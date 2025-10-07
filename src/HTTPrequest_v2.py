#!/usr/bin/env python3

"""
for further considerations for middelware:
https://www.starlette.io/middleware/#__tabbed_1_1
"""
import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Scope, Receive, Send

# internal
from fronius2influx import (StatusDevice, StatusBattery, VisibleDevice,
                            StatusErrors)
from fronius_aux import MYFORMAT
from fronius_ws_sync_client import WEBSOCKET_PORT, WEBSOCKET_ENDPOINT

logging_level: str = "INFO"
logging.basicConfig(format=MYFORMAT,
                    level=getattr(logging, logging_level),
                    datefmt="%Y-%m-%d %H:%M:%S")

class PostProcess:
    def __init__(self):
        self._message = list()
        self._battery = dict()
        self._wallbox = dict()
        self._smartmeter = dict()
        self._inverter = dict()
        self._devicestatus = dict()

    def __assign(self):
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
                    self._devicestatus = i['fields']

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, item):
        for k, v in self.__dict__.items():
            if isinstance(v, dict): super().__setattr__(k, dict())
        self._message = json.loads(item)
        self.__assign()

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
    def devicestatus(self):
        return self._devicestatus


class ConnectionManager:
    """Class defining socket events"""
    def __init__(self):
        self.active_connections = list()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(
            "Client {} connected, out of {} websocket connection(s).".format(
                websocket.client,
                len(self.active_connections)
            ))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logging.warning("Waiting for client to reconnect ...")

    async def send_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)


class ASGIMiddleware:
    def __init__(self, app_c: ASGIApp):
        self.app = app_c

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return
        # code to perform on ws call
        # print(scope, receive, send)
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app_c: FastAPI):
    # on start
    logging.info("Waiting for client to connect.")
    yield
    # on shutdown
    pass


pp = PostProcess()
manager = ConnectionManager()
app = FastAPI(title="Fronius Inverter Direct Readout",
              description="Current values from the Fronius Inverter & Wallbox",
              lifespan=lifespan,
              middleware=[Middleware(ASGIMiddleware),])


def relu(x: float) -> float: return max(0., x)


@app.websocket(WEBSOCKET_ENDPOINT)  # websocket endpoint
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pp.message = data  # assign data
            await manager.send_message(data, websocket)  # resend for confirmation
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/retrieve",
         description="Testing the message content"
         )
async def retrieve():

    return JSONResponse(
        content=pp.message,
        status_code=status.HTTP_200_OK)


@app.get("/query/battery")
async def query_battery() -> None:
    try:
        result: dict[str, float] = {
            "BatteryLoadingLevel": pp.battery['StateOfCharge_Relative'],
            "Temperature_Cell" : pp.battery['Temperature_Cell']
        }
    except KeyError:
        return JSONResponse(
            content={},
            status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/power")
async def query_power() -> None:
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


@app.get("/query/status")
async def query_status() -> None:
    try:
        result: dict[str, str] = {
            "Smart Meter Status":
                StatusDevice(int(pp.smartmeter['Enable'])).name,
            "Smart Meter Visible":
                VisibleDevice(int(pp.smartmeter['Visible'])).name,
            "Inverter ErrorCode":
                StatusErrors(pp.devicestatus['ErrorCode']).name,
            "Inverter State":
                pp.devicestatus['InverterState'],
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


@app.get("/query/wallbox_status")
async def query_wallbox_status() -> None:
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
                "Wallbox power (Ampere)": pp.wallbox['Wallbox power (Ampere)']
            }
        except KeyError:
            return JSONResponse(
                content=result,
                status_code=status.HTTP_206_PARTIAL_CONTENT)

    return JSONResponse(
        content=result,
        status_code=status.HTTP_200_OK)


@app.get("/query/wallbox_power")
async def query_wallbox_power() -> None:
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


def main():
    config = {
        "host": "0.0.0.0",
        "port": WEBSOCKET_PORT,
        "timeout_keep_alive": 60,
        "log_level": "warning"
    }
    # kick off Asynchronous Server Gateway Interface (ASGI) webserver
    uvicorn.run(app=app,
                **config,
                )


if __name__ == '__main__':
    main()
