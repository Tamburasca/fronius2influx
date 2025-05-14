#!/usr/bin/env python3

from typing import Any
# internal
from src.wattpilot import Wattpilot
from src.fronius_aux import current_time_utc


def wattpilot_get(
        wallbox: Wattpilot = None
) -> list[dict[str, str | dict]]:
    result = list()
    if wallbox:
        if wallbox.connected:
            result = [
                {
                    "measurement": "Wallbox",
                    "time": current_time_utc(),
                    # ToDo: yet to verify fields required!
                    "fields": {
                        "power": wallbox.power,
                        "power1": wallbox.power1,
                        "power2": wallbox.power2,
                        "power3": wallbox.power3,
                        "powerN": wallbox.powerN
                    }
                }
            ]

    return result


def wattpilot_status(
        wallbox: Wattpilot = None
) -> list[dict[str, Any]]:
    fields = {"Wallbox connected": False}
    if wallbox:
        if wallbox.connected:
            # print(wallbox.__dict__)
            fields = {
                "Wallbox connected": True,
                "Car connected": wallbox.carConnected,
                "Charge status": wallbox.AllowCharging,
                "Wallbox mode": wallbox.mode,
                "Wallbox power (Ampere)": wallbox.amp
            }
    result = [
        {
            'measurement': 'Wallbox',
            'time': current_time_utc(),
            'fields': fields
        }
    ]

    return result
