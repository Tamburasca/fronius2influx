#!/usr/bin/env python3

"""
Rest API for Grafana Dashboard "Current Reading"
Data is exchanged from fronius2influx.py via websockets

for further considerations of middleware:
https://www.starlette.io/middleware/#__tabbed_1_1
"""
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

import requests
import uvicorn
from fastapi import FastAPI, status, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Scope, Receive, Send

# internal
from hcpy.hc_aux import read_secrets, asset_url, ProgramsEnum
from src.__init__ import __version__
from src.fronius_aux import (
    StatusDevice,
    StatusBattery,
    VisibleDevice,
    StatusErrors,
    MYFORMAT
)

logging_level: str = "INFO"
logging.basicConfig(format=MYFORMAT,
                    level=getattr(logging, logging_level),
                    datefmt="%Y-%m-%d %H:%M:%S")

parameter_file = "{}/data/parameter.json".format(
    os.path.dirname(
        os.path.realpath(__file__)
    ))
with open(parameter_file, 'r') as f:
    parameter = json.load(f)


class HC:
    def __init__(self) -> None:
        self.active: bool = False
        self.processed: bool = False
        self.program: str = ""
        self.program_name: str = ""
        self.percentage: int = 99
        self.code: int = status.HTTP_200_OK
        self.msg: str = "Request submitted. Battery level is yet to low."

    def reset(self) -> None:
        self.active = True  # supersede any previous requests
        self.processed = False
        self.code: int = status.HTTP_200_OK
        self.msg: str = "Request submitted. Battery level is yet to low."


hc = HC()


class PostProcess:
    def __init__(self) -> None:
        self._message = list()
        self._battery = dict()
        self._wallbox = dict()
        self._smartmeter = dict()
        self._inverter = dict()
        self._device_status = dict()

    def __assign(self) -> None:
        """

        :return:
        """
        for v in self.__dict__.values():  # reset all dict
            if isinstance(v, dict): v.clear()

        for i in self._message:
            match i.get('measurement'):
                case "Battery":
                    self._battery = i['fields']
                case "Wallbox":  # we got two wallbox items!
                    self._wallbox.update(i['fields'])
                case "SmartMeter":
                    self._smartmeter = i['fields']
                case "CommonInverterData":
                    self._inverter = i['fields']
                case "DeviceStatus":
                    self._device_status = i['fields']

    def __start_dishwasher(self) -> None:
        """

        :return:
        """
        if hc.active:
            if self._battery['StateOfCharge_Relative'] >= hc.percentage:
                secrets = read_secrets()
                headers = {
                    "Authorization": "Bearer " + secrets['data']['access_token'],
                    "accept": "application/vnd.bsh.sdk.v1+json",
                    "Accept-Language": "en-US",
                    "Content-Type": "application/vnd.bsh.sdk.v1+json"
                }
                payload = {
                    "data": {
                        "key": hc.program
                    }
                }
                r = requests.put(
                    asset_url + "/" + secrets['Dishwasher']['haId'] + "/programs/active",
                    headers=headers,
                    json=payload
                )
                if r.status_code != requests.codes.no_content:
                    msg = f"Error to start program '{hc.program_name}'."
                    logging.warning(msg=msg)
                    logging.warning(msg="Status_code: " + str(r.status_code))
                    logging.warning(msg="Status_text: " + r.text)
                    hc.code = r.status_code
                    hc.msg = msg + str("\nStatus_text: " + r.text)
                else:
                    msg = f"Program '{hc.program_name}' started."
                    logging.info(msg=msg)
                    logging.info(msg="Status_code: " + str(r.status_code))
                    logging.info(msg="Status_text: " + r.text)
                    hc.msg = msg

                hc.active = False
            hc.processed = True

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, item):
        self._message = json.loads(item)
        self.__assign()
        self.__start_dishwasher()

    @property
    def battery(self):
        return self._battery

    @property
    def wallbox(self):
        return self._wallbox

    @property
    def smartmeter(self):
        return self._smartmeter

    @property
    def inverter(self):
        return self._inverter

    @property
    def device_status(self):
        return self._device_status


class ConnectionManager:
    """Class defining socket events.
    Supposedly we will have one ws connection solely
    """

    def __init__(self) -> None:
        self.active_connection: bool = False

    async def connect(
            self,
            websocket: WebSocket
    ) -> None:
        await websocket.accept()
        self.active_connection = True
        logging.info(f"Client '{websocket.client}' connected.")

    def disconnect(
            self,
            websocket: WebSocket
    ) -> None:
        self.active_connection = False
        logging.info(f"Client '{websocket.client}' disconnected. Waiting to "
                     f"reconnect ...")

    async def send_message(
            self,
            websocket: WebSocket,
            message: str
    ) -> None:
        await websocket.send_text(message)


class ASGIMiddleware:
    """ serves as placeholder, not of any benefit for the time being
    """

    def __init__(
            self,
            app_c: ASGIApp
    ) -> None:
        self.app = app_c

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send
    ) -> None:
        if scope["type"] == "websocket":
            # possible code to perform on a ws call, not utilized to date
            # print(scope, receive, send)
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app_c: FastAPI) -> AsyncGenerator[None, None]:
    # on start
    logging.info("Waiting for client to connect.")
    yield
    # on shutdown
    pass


def relu(x: float) -> float: return max(0., x)


pp = PostProcess()
manager = ConnectionManager()
app = FastAPI(title="Fronius Inverter Direct Readout",
              description="Current Readings from the Inverter & Wallbox",
              lifespan=lifespan,
              middleware=[Middleware(ASGIMiddleware), ]  # type: ignore[arg-type]
              )


@app.websocket(parameter['RestAPI']['websocket'])  # websocket endpoint
async def websocket_endpoint(websocket: WebSocket) -> None:
    """

    :param websocket:
    :return:
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pp.message = data  # assign data
            await manager.send_message(websocket, data)  # resend for confirmation
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/query/debug",
         name="Debugging entire content",
         tags=["debugging"]
         )
async def debug() -> JSONResponse:
    return JSONResponse(
        content=pp.message,
        status_code=status.HTTP_200_OK)


@app.get("/query/battery",
         name="Battery measurements",
         tags=["readings"])
async def query_battery() -> JSONResponse:
    """

    :return:
    """
    try:
        result: dict[str, float] = {
            "BatteryLoadingLevel": pp.battery['StateOfCharge_Relative'],
            "Temperature_Cell": pp.battery['Temperature_Cell']
        }
    except KeyError:
        return JSONResponse(
            content={},
            status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/power",
         name="Energy measurements",
         tags=["readings"])
async def query_power() -> JSONResponse:
    """

    :return:
    """
    try:
        result: dict[str, float] = {
            "SolarDC":
                (pp.inverter['IDC'] * pp.inverter['UDC']
                 + pp.inverter['IDC_2'] * pp.inverter['UDC_2'])
        }
        power_net = pp.smartmeter['PowerReal_P_Sum']
        pac = pp.inverter['PAC']
        battery = pp.battery['Voltage_DC'] * pp.battery['Current_DC']
        result['Consumed'] = relu(pac + power_net)
        if power_net <= 0.:
            result['Net To'] = -power_net
        else:
            result['Net From'] = power_net
        if battery >= 0.:
            result["Battery Charging"] = battery
        else:
            result["Battery Discharging"] = -battery
    except KeyError:
        return JSONResponse(
            content={},
            status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/status",
         name="Status",
         tags=["status"])
async def query_status() -> JSONResponse:
    """

    :return:
    """
    try:
        result: dict[str, str] = {
            "Smart Meter Status":
                StatusDevice(int(pp.smartmeter['Enable'])).name,
            "Smart Meter Visible":
                VisibleDevice(int(pp.smartmeter['Visible'])).name,
            "Inverter ErrorCode":
                StatusErrors(pp.device_status['ErrorCode']).name,
            "Inverter State":
                pp.device_status['InverterState'],
            "Battery Status":
                StatusDevice(int(pp.battery['Enable'])).name,
            "Battery Status Cell":
                StatusBattery(int(pp.battery['Status_BatteryCell'])).name
        }
    except KeyError:
        return JSONResponse(
            content={},
            status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/wallbox_status",
         name="Wallbox status",
         tags=["wallbox"])
async def query_wallbox_status() -> JSONResponse:
    """

    :return:
    """
    v = pp.wallbox.get('Wallbox connected', False)
    result: dict[str, float | bool | str] = {
        "Wallbox connected": v
    }
    if v:
        try:
            result = result | {
                "Car connected": pp.wallbox['Car connected'],
                "Charge status": pp.wallbox['Charge status'],
                "Wallbox mode": pp.wallbox['Wallbox mode'],
                "Wallbox current": pp.wallbox['Wallbox current']
            }
        except KeyError:
            return JSONResponse(
                content=result,
                status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/wallbox_power",
         name="Wallbox power readings",
         tags=["wallbox"])
async def query_wallbox_power() -> JSONResponse:
    """

    :return:
    """
    result: dict[str, float] = dict()
    v = pp.wallbox.get('Wallbox connected', False)
    if v:
        try:
            result: dict[str, float] = {
                "power": pp.wallbox["power"],
                "power1": pp.wallbox["power1"],
                "power2": pp.wallbox["power2"],
                "power3": pp.wallbox["power3"],
                "powerN": pp.wallbox["powerN"]
            }
        except KeyError:
            return JSONResponse(
                content={},
                status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/app_version",
         name="Application Version",
         tags=["status"])
async def query_version() -> JSONResponse:
    result: dict[str, str] = {
        "Version": __version__
    }
    """
    Display current version
    """
    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.put("/HomeConnect/start",
         summary="Start Dishwasher",
         description="Start the Dishwasher if battery loading level is exceeded.",
         tags=["HomeConnect"]
         )
def start_dishwasher(
        program_id: Annotated[
            ProgramsEnum,
            Query(description="Program ID")
        ],
        battery_loading_level: Annotated[
            int,
            Query(
                description="Battery loading level (%) beyond to start Dishwasher",
                ge=25,
                le=100)
        ] = 99  # default
) -> PlainTextResponse:
    """
    Start Dishwasher.
    :param program_id:
    :param battery_loading_level:
    :return:
    """
    hc.reset()

    hc.program = program_id.name
    hc.program_name = program_id.value
    hc.percentage = battery_loading_level

    while not hc.processed:
        time.sleep(1.)

    return PlainTextResponse(
        content=hc.msg,
        status_code=hc.code)


def main() -> None:
    """

    :return:
    """
    config = {
        "host": "0.0.0.0",
        "port": parameter['RestAPI']['port'],  # one port for ws and http Rest API
        "timeout_keep_alive": 60,
        "log_level": "warning"
    }
    # kick off Asynchronous Server Gateway Interface (ASGI) webserver
    uvicorn.run(app=app,
                **config,
                )


if __name__ == '__main__':
    main()
