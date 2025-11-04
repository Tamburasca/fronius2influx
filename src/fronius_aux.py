#!/usr/bin/env python3

import math
import os
from datetime import datetime, timezone
from enum import Enum, EnumMeta
from typing import Any
from typing import Generator

from cryptography.fernet import Fernet

# The ASTM G-173 standard measures solar intensity over the band 280 to 4000 nm
SOLAR_CONSTANT = 1_347.9  # W m⁻²

MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - %(name)s - "
                 "%(lineno)s - %(funcName)s()\t%(message)s")


class VisibleDevice(Enum):
    Outdated = 0
    ValuesOK = 1


class StatusDevice(Enum):
    Disconnected = 0
    Managed = 1


class StatusErrors(Enum):
    OK = 0
    NotImplemented = 1
    Uninitialized = 2
    Initialized = 3
    Running = 4
    Timeout = 5
    ArgumentError = 6
    LNRequestError = 7
    LNRequestTimeout = 8
    LNParseError = 9
    ConfigIOError = 10
    NotSupported = 11
    DeviceNotAvailable = 12
    UnknownError = 255
    Sleeping = 1175


class StatusBattery(Enum):  # ToDo replace float through string in influxDB?
    STANDBY = 0
    INACTIVE = 1
    DARKSTART = 2
    ACTIVE = 3
    FAULT = 4
    UPDATING = 5


class StatusCode(str, Enum):  # ToDo: needed?
    A0 = "Startup", 0
    A1 = "Startup", 1
    A2 = "Startup", 2
    A3 = "Startup", 3
    A4 = "Startup", 4
    A5 = "Startup", 5
    A6 = "Startup", 6
    B = "Running", 7
    C = "Standby", 8
    D = "Bootloading", 9
    E = "Error", 10
    F = "idle", 11
    G = "Ready", 12
    H = "Sleeping", 13
    I = "Unknown", 255

    def __new__(
            cls,
            value,
            key
    ) -> Enum:
        obj = str.__new__(cls, [str, int])
        obj._value_ = key
        obj.__n = value
        return obj

    @property
    def value(self):
        return self.__n


class _Meta(EnumMeta):
    def __iter__(self) -> Generator[str, None, None]:
        for member in super().__iter__():
            yield "http://{}{}{}".format(
                member.kwargs['host'],
                member.kwargs['application'],
                member.value
            )


class Math:
    @classmethod
    def sindeg(cls, deg: float) -> float: return math.sin(math.radians(deg))

    @classmethod
    def cosdeg(cls, deg: float) -> float: return math.cos(math.radians(deg))

    @classmethod
    def asindeg(cls, r: float) -> float: return math.degrees(math.asin(r))


def air_mass(
        elevation: float,
        altitude: float
) -> tuple[float, float]:
    """
    calculate air mass attenuation
    https://www.pveducation.org/pvcdrom/properties-of-sunlight/air-mass#AMequation
    air_mass = 1. / math.cos(math.radians(90. - el))
    The Kasten and Young formula was originally given in terms of
    elevation as follows
    :param elevation: sun elevation angle in degrees
    :param altitude: altitude of location in meters
    :return:
    air mass attenuation factor,
    air mass
    """
    a = 0.00014 * altitude  # altitude correction factor
    air_mass_revised = 1. / (
            Math.cosdeg(90. - elevation) + 0.50572 * (6.07995 + elevation) ** -1.6364
    )
    return (
        (1. - a) * 0.7 ** (air_mass_revised ** 0.678) + a,
        air_mass_revised
    )


def direct_radiation_on_tilted_surface(
        elevation: float,
        azimuth: float,
        inclination: float,
        orientation: float,
) -> float:
    """
    calculate angle between direct radiation and perpendicular line
    of tilted PV surface
    https://www.pveducation.org/pvcdrom/properties-of-sunlight/arbitrary-orientation-and-tilt
    :param elevation: sun elevation angle in degrees
    :param azimuth: sun azimuth angle in degrees
    :param inclination: panel inclination in degrees
    :param orientation: panel orientation in degrees
    :return: 
    """
    return max(
        Math.cosdeg(elevation)
        * Math.sindeg(inclination)
        * Math.cosdeg(orientation - azimuth)
        + Math.sindeg(elevation)
        * Math.cosdeg(inclination),
        0.
    )


def current_time_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec='seconds')


def flatten_json(y: dict) -> dict[str, Any]:
    """
    https://towardsdatascience.com/flattening-json-objects-in-python-f5343c794b10
    :param y: semi-structured JSON object
    :return: flattened JSON object
    """
    out: dict[str, Any] = dict()

    def flatten(x, name='') -> dict[str, Any]:
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '_')
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '_')
                i += 1
        else:
            out[name[:-1]] = x

    flatten(y)

    return out


def get_secret(
        key: str,
        default: str = ''
) -> str:
    """
    fetch any PW from file, otherwise PW is default
    :param key: filename that contains token - as provided in docker-compose
    :param default: default PW
    :return: PW
    """
    value = os.getenv(key, default)
    if os.path.isfile(value):
        with open(value) as f:
            return f.read()
    return value


def pw(
        pw_encoded: str,
        cipher: str
) -> str:
    """
    decrypts application key via cryptography.Fernet()
    :param pw_encoded: string
        encoded application key
    :param cipher: string
        decrypt key
    :return:
        str: decoded application key
    """
    if cipher is None:
        raise Exception("Please set the environment variable MOSQUITTO_CIPHER")
    return Fernet(str.encode(cipher)).decrypt(str.encode(pw_encoded)).decode()
