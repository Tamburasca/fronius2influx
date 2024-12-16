#!/usr/bin/env python3

from datetime import datetime, timezone
# internal
from src.wattpilot import Wattpilot


def wattpilot_get(wallbox: Wattpilot=None) -> list[dict[str, str | dict]]:
    result: list = list()
    if wallbox:
        if wallbox.connected:
            t = datetime.now(timezone.utc).isoformat(timespec='seconds')
            result = [
                {
                    'measurement': 'Wallbox',
                    'time': t,
                    # ToDo: yet verify fields to be archived!
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