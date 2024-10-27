#!/usr/bin/env python3

import pytz
import datetime
# internal
from src.wattpilot import Wattpilot


def wattpilot_get(wallbox: Wattpilot=None) -> list[dict[str, str | dict]]:
    result = []
    if wallbox:
        if wallbox.connected:
            result = [
                {
                    'measurement': 'Wallbox',
                    'time': datetime.datetime.now(
                        tz=pytz.utc
                    ).isoformat(
                        timespec='seconds'
                    ),
                    'fields': {
                        "power": wallbox.power,
                        "power1": wallbox.power1,
                        "power2": wallbox.power2,
                        "power3": wallbox.power3,
                        "powerN": wallbox.powerN
                    }
                }
            ]

    return result