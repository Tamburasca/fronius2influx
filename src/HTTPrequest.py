#!/usr/bin/env python3

import os
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from requests import get, HTTPError, Response
# internal
from fronius2influx import FroniusToInflux, FroniusEndpoints


parameter_file = "{}/data/parameter.json".format(
    os.path.dirname(os.path.realpath(__file__))
)
with open(parameter_file, 'r') as f:
    parameter = json.load(f)

endpoints = FroniusEndpoints.get_endpoints(
    host=parameter['server']['host'],
    application=parameter['server']['application']
)
z = FroniusToInflux(
    client=None,  # dummy
    parameter=parameter,
    endpoints=endpoints,
    wallbox=None,  # dummy
    dry_run=True
)

app = FastAPI()


def relu(x) -> float: return max(0.0, x)


def get_request() -> list:
    result: Response = None
    c = list()
    for url in endpoints:
        try:
            result = get(url)
            result.raise_for_status()  # HTTP status
            z.data = result.json()
            c.extend(z.translate_response())
        except HTTPError:
            raise HTTPException(status_code=400,
                                detail="response: {}".format(result))

    return c


@app.get("/query/battery")
async def query_battery() -> None:
    res: dict[str, float] = dict()
    for item in get_request():
        if item.get("measurement") == "Battery":
            for i in ["Voltage_DC", "Current_DC", "StateOfCharge_Relative", "Temperature_Cell"]:
                res[i] = item['fields'][i]

    res['BatteryLoadingLevel'] = res.pop('StateOfCharge_Relative')
    res.pop('Voltage_DC')
    res.pop('Current_DC')
    # res['PowerBattery'] = res.pop('Voltage_DC') * res.pop('Current_DC')

    return JSONResponse(
        content=res,
        status_code=200)


@app.get("/query/power")
async def query_power() -> None:
    res: dict[str, float] = dict()
    for item in get_request():
        match item.get("measurement"):
            case "SmartMeter":
                for i in ['PowerReal_P_Sum']:
                    res[i] = item['fields'][i]
            case "CommonInverterData":
                for i in ["UDC", "IDC", "UDC_2", "IDC_2", "PAC"]:
                    res[i] = item['fields'][i]
            case "Battery":
                for i in ["Voltage_DC", "Current_DC"]:
                    res[i] = item['fields'][i]

    battery = res.pop('Voltage_DC') * res.pop('Current_DC')
    if battery >= 0.:
        res["Battery Charging"] = battery
    else:
        res["Battery Discharging"] = -battery
    power_net = res.pop('PowerReal_P_Sum')
    if power_net <= 0.:
        res['Net To'] = -power_net
    else:
        res['Net From'] = power_net
    res['SolarDC'] = (res.pop('IDC') * res.pop('UDC')
                      + res.pop('IDC_2') * res.pop('UDC_2'))
    res['Consumed'] = relu(res.pop('PAC') + power_net)

    return JSONResponse(
        content=res,
        status_code=200)


def main():
    config = {
        "host": "0.0.0.0",
        "port": 5000,
        "timeout_keep_alive": 60,
        "log_level": "warning"
    }
    # kick off Asynchronous Server Gateway Interface web server
    uvicorn.run(app=app,
                **config,
                )


if __name__ == '__main__':
    main()
