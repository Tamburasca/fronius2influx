#!/usr/bin/env python3

import datetime
import json
import math
import pytz
import os
import sys
import logging
from timeit import default_timer
from enum import Enum, EnumMeta
from time import sleep
from typing import Generator
from astral import LocationInfo
from astral.sun import elevation, azimuth
from influxdb_client import InfluxDBClient, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
from requests import get
from requests.exceptions import ConnectionError, HTTPError
# internal imports
from src.fronius_aux import flatten_json, get_secret, pw
from src.wattpilot_read import wattpilot_get
from src.wattpilot import Wattpilot

# Logging Format
MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - %(name)s - "
                 "%(lineno)s - %(funcName)s()\t%(message)s")

MOSQUITTO_CIPHER = os.environ.get('MOSQUITTO_CIPHER')


class WrongFroniusData(Exception): ...


class SunIsDown(Exception): ...


class DataCollectionError(Exception): ...


class DeviceStatus(Exception): ...


class _Meta(EnumMeta):
    def __iter__(self) -> Generator[str, None, None]:
        for member in super().__iter__():
            yield "http://{}{}{}".format(
                member.kwargs['host'],
                member.kwargs['application'],
                member.value
            )


class FroniusEndpoints(
    str,
    Enum,
    metaclass=_Meta
):
    """
    Cool hack on EnumMeta, just for kicks, pushing it to the limits!
    A list comprehension would have solved it better of course, such as:
    endpoints = [("http://{0}{1}" + member.value).format(
        parameter['server']['host'],
        parameter['server']['application']
    ) for member in FroniusEndpoints]
    """
    INVERTER_REAL_TIME_DATA = "GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=1"
    STORAGE_REAL_TIME_DATA = "GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0"
    METER_REAL_TIME_DATA = "GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0"
    # OBSOLETE = "GetInverterRealtimeData.cgi?Scope=Device&DataCollection=3PInverterData&DeviceId=1"

    @classmethod
    def get_endpoints(cls, **kwargs) -> Enum:
        cls.kwargs = kwargs
        return cls


class FroniusToInflux(object):
    BACKOFF_INTERVAL = 5  # GET request every BACKOFF_INTERVAL seconds
    WRITE_CYCLE = 12  # write every WRITE_CYCLE th cycle
    SOLAR_CONSTANT = 1_361  # W m⁻²
    A = 0.00014  # constant / m⁻¹

    def __init__(
            self,
            *,
            client: InfluxDBClient,
            parameter: dict,
            endpoints: list[str],
            wallbox: Wattpilot,
            **kwargs
    ):
        self.client = client
        self.write = client.write_api(  # batch mode
            # write_options=WriteOptions(flush_interval=1_000)  # flush after 1s
            write_options=WriteOptions(SYNCHRONOUS)
        )
        self.endpoints = endpoints
        self.parameter = parameter
        self.wallbox = wallbox
        self.location = LocationInfo(
            name=parameter['location']['city'],
            region=parameter['location']['region'],
            latitude=parameter['location']['latitude'],
            longitude=parameter['location']['longitude'],
            timezone=parameter['location']['timezone']
        )
        self.data: dict = dict()
        self.ignore_sun_down: bool = False
        self.dry_run: bool = kwargs.get('dry_run', False)

    def get_float_or_zero(
            self,
            value: str
    ) -> float:
        try:
            internal_data: dict[str, dict] = self.data['Body']['Data']
        except KeyError:
            raise WrongFroniusData('Response structure is not healthy.')

        return 0. if 'Value' not in internal_data.get(value, {}) \
                     or internal_data.get(value, {}).get('Value') is None \
            else float(internal_data.get(value)['Value'])

    def translate_response(self) -> list[dict[str, str | dict]]:
        collection = self.data['Head']['RequestArguments'].get('DataCollection')
        timestamp = self.data['Head']['Timestamp']
        try:
            storage = \
                self.data['Body']['Data']['Controller']['Details']['Model']
        except KeyError:
            storage = None
        try:
            meter = self.data['Body']['Data']['Details']['Model']
        except KeyError:
            meter = None

        if collection == 'CommonInverterData':
            device_status = self.data['Body']['Data']['DeviceStatus']
            return [
                {
                    'measurement': 'DeviceStatus',
                    'time': timestamp,
                    'fields': {
                        'ErrorCode': device_status['ErrorCode'],
                        'InverterState': device_status['InverterState'],
                        'StatusCode': device_status['StatusCode']
                    }
                },
                {
                    'measurement': collection,
                    'time': timestamp,
                    'fields': {
                        'PAC': self.get_float_or_zero('PAC'),
                        'SAC': self.get_float_or_zero('SAC'),
                        'IAC': self.get_float_or_zero('IAC'),
                        'UAC': self.get_float_or_zero('UAC'),
                        'FAC': self.get_float_or_zero('FAC'),
                        'IDC': self.get_float_or_zero('IDC'),
                        'IDC_2': self.get_float_or_zero('IDC_2'),
                        'UDC': self.get_float_or_zero('UDC'),
                        'UDC_2': self.get_float_or_zero('UDC_2'),
                        'DAY_ENERGY': self.get_float_or_zero('DAY_ENERGY'),
                        'YEAR_ENERGY': self.get_float_or_zero('YEAR_ENERGY'),
                        'TOTAL_ENERGY': self.get_float_or_zero('TOTAL_ENERGY'),
                    }
                }
            ]

        elif collection == '3PInverterData':
            return [
                {
                    'measurement': collection,
                    'time': timestamp,
                    'fields': {
                        'IAC_L1': self.get_float_or_zero('IAC_L1'),
                        'IAC_L2': self.get_float_or_zero('IAC_L2'),
                        'IAC_L3': self.get_float_or_zero('IAC_L3'),
                        'UAC_L1': self.get_float_or_zero('UAC_L1'),
                        'UAC_L2': self.get_float_or_zero('UAC_L2'),
                        'UAC_L3': self.get_float_or_zero('UAC_L3'),
                    }
                }
            ]

        elif collection is None and storage == "BYD Battery-Box Premium HV":
            c = self.data['Body']['Data']['Controller']
            return [
                {
                    'measurement': "Battery",
                    'time': timestamp,
                    'fields': {
                        'Current_DC': float(c.get(
                            'Current_DC', 0.)),
                        'Enable': c.get('Enable', -1),
                        'StateOfCharge_Relative': float(c.get(
                            'StateOfCharge_Relative', -1.)),
                        'Status_BatteryCell': float(c.get(
                            'Status_BatteryCell', -1.)),
                        'Temperature_Cell': float(c.get(
                            'Temperature_Cell', -1.)),
                        'Voltage_DC': float(c.get('Voltage_DC', 0.))
                    }
                }
            ]

        elif collection is None and meter == "Smart Meter TS 65A-3":
            m = self.data['Body']['Data']
            return [
                {
                    'measurement': "SmartMeter",
                    'time': timestamp,
                    'fields': {
                        'Enable': m.get(
                            'Enable', -1),
                        'PowerReal_P_Sum': float(m.get(
                            'PowerReal_P_Sum', 0.)),
                        'PowerReal_P_Phase_1': float(m.get(
                            'PowerReal_P_Phase_1', 0.)),
                        'PowerReal_P_Phase_2': float(m.get(
                            'PowerReal_P_Phase_2', 0.)),
                        'PowerReal_P_Phase_3': float(m.get(
                            'PowerReal_P_Phase_3', 0.)),
                        'Current_AC_Sum': float(m.get(
                            'Current_AC_Sum', 0.)),
                        'Current_AC_Phase_1': float(m.get(
                            'Current_AC_Phase_1', 0.)),
                        'Current_AC_Phase_2': float(m.get(
                            'Current_AC_Phase_2', 0.)),
                        'Current_AC_Phase_3': float(m.get(
                            'Current_AC_Phase_3', 0.)),
                        'Voltage_AC_Phase_1': float(m.get(
                            'Voltage_AC_Phase_1', 0.)),
                        'Voltage_AC_Phase_2': float(m.get(
                            'Voltage_AC_Phase_2', 0.)),
                        'Voltage_AC_Phase_3': float(m.get(
                            'Voltage_AC_Phase_3', 0.)),
                    }
                }
            ]

        else:
            raise DataCollectionError("Unknown data collection type.")

    def sun_parameter(self) -> list[dict[str, str | dict]]:
        el = elevation(observer=self.location.observer,
                       with_refraction=True)
        if el > 0:
            az = azimuth(observer=self.location.observer)
            altitude = self.parameter["location"]["altitude"]["value"]
            # https://www.pveducation.org/pvcdrom/properties-of-sunlight/air-mass#AMequation
            # air_mass = 1. / math.cos(math.radians(90. - el))
            # The Kasten and Young formula was originally given in terms of
            # altitude el as
            air_mass_revised = 1. / (
                    math.cos(math.radians(90. - el))
                    + 0.50572 * (6.07995 + el) ** -1.6364
            )
            air_mass_attenuation = (
                    (1. - self.A * altitude) * 0.7 ** air_mass_revised ** 0.678
                    + self.A * altitude
            )
            # Direct beam intensity / W m⁻²
            intens = self.SOLAR_CONSTANT * air_mass_attenuation
            result: dict[str, float | None] = {
                "sun_elevation": el,
                "sun_azimuth": az,
                "air_mass": air_mass_revised,
                "atmospheric_attenuation": air_mass_attenuation
            }
            logging.debug("sun elevation: {0} deg, "
                          "sun azimuth: {1} deg, "
                          "air mass: {2}, "
                          "air mass attenuation: {3}".format(
                el,
                az,
                air_mass_revised,
                air_mass_attenuation))
            for item, value in self.parameter['housetop'].items():
                # https://www.pveducation.org/pvcdrom/properties-of-sunlight/arbitrary-orientation-and-tilt
                r = max(
                    math.cos(math.radians(el))
                    * math.sin(math.radians(value['inclination']['value']))
                    * math.cos(math.radians(value['orientation']['value'] - az))
                    + math.sin(math.radians(el))
                    * math.cos(math.radians(value['inclination']['value'])),
                    0.
                )
                incidence_angle_sun = math.degrees(math.asin(r))
                logging.debug("{0}, "
                              "incidence angle: {1} deg, "
                              "incidence factor: {2}, "
                              "true irradiation: {3} Wm⁻²".format(
                    item,
                    incidence_angle_sun,
                    r,
                    intens * r))
                result[item] = {
                    "intensity_corr_area_eff": intens
                                               * value['area']['value']
                                               * value['efficiency']['value'],
                    "incidence_ratio": r
                }
            return [
                {
                    'measurement': 'SolarData',
                    'time': datetime.datetime.now(
                        tz=pytz.utc
                    ).isoformat(
                        timespec='seconds'
                    ),
                    'fields': flatten_json(result)
                }
            ]
        else:
            if not self.ignore_sun_down:
                raise SunIsDown
            else:
                return []

    def run(self) -> None:
        flag_sun_is_down: bool = False
        flag_connection: bool = False
        flag_exception: bool = False
        collected_data: list[dict[str, str | dict]] = list()
        counter = 1

        try:
            while True:
                try:
                    for url in self.endpoints:
                        result = get(url)
                        result.raise_for_status()  # HTTP status
                        self.data = result.json()
                        collected_data.extend(self.translate_response())
                    # amend solar parameter
                    collected_data.extend(self.sun_parameter())
                    # amend wallbox data
                    if self.parameter['wallbox']['active']:
                        collected_data.extend(
                            wattpilot_get(wallbox=self.wallbox)
                        )

                    if counter >= self.WRITE_CYCLE:
                        if logging.DEBUG >= logging.root.level:
                            print(collected_data)
                        if not self.dry_run:
                            start_time = default_timer()
                            self.write.write(
                                bucket="Fronius",
                                org="Fronius",
                                record=collected_data,
                                write_precision='s'
                            )
                            logging.debug(
                                "Time consumed for influxDB "
                                "Sync Write API': {0:.2f} ms".format(
                                    (default_timer() - start_time) * 1_000))
                        collected_data.clear() # faster than assign new list
                        counter = 1
                    else:
                        counter += 1

                    flag_sun_is_down = False
                    flag_connection = False
                    flag_exception = False
                    sleep(self.BACKOFF_INTERVAL)
                except SunIsDown:
                    if not flag_sun_is_down:
                        logging.warning("Waiting for sun to rise ...")
                        flag_sun_is_down = True
                    sleep(60)
                except (ConnectionError, HTTPError, DeviceStatus) as e:
                    if not flag_connection:
                        logging.error("Connection or HTTP error: {}".format(e))
                        logging.warning(
                            "Please check your Fronius Inverter. "
                            "Waiting 10 s for exception to suspend ..."
                        )
                        flag_connection = True
                    sleep(10)
                except Exception as e:
                    if not flag_exception:
                        logging.error("Unknown exception: {}".format(e))
                        logging.warning(
                            "Waiting 10 s for exception to suspend ..."
                        )
                        flag_exception = True
                    self.data = dict()
                    sleep(10)

        except KeyboardInterrupt:
            print("Finishing. Goodbye!")
            sys.exit(os.EX_OK)
        except (Exception,):
            sys.exit(os.EX_OSERR)


def main() -> None:
    wallbox: Wattpilot = None

    parameter_file = "{}/data/parameter.json".format(
        os.path.dirname(os.path.realpath(__file__))
    )
    with open(parameter_file, 'r') as f:
        parameter = json.load(f)

    logging_level: str = "DEBUG" if parameter['debug'] else "INFO"
    logging.basicConfig(format=MYFORMAT,
                        level=getattr(logging, logging_level),
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.getLogger("Rx").setLevel(logging.INFO)

    influxdb_host = os.getenv('INFLUXDB_HOST',
                              parameter['influxdb']['host'])
    influxdb_port = int(os.getenv('INFLUXDB_PORT',
                                  parameter['influxdb']['port']))
    # default applies, if runs outside Docker
    influxdb_token_write = get_secret('INFLUXDB_TOKEN_FILE',
                                      os.getenv('INFLUXDB_TOKEN'))

    client = InfluxDBClient(
        url="http://{0}:{1}".format(influxdb_host,
                                    influxdb_port),
        token=influxdb_token_write,
        org=parameter['influxdb']['organization'],
        verify_ssl=parameter['influxdb']['verify_ssl']
    )

    endpoints = FroniusEndpoints.get_endpoints(
        host=parameter['server']['host'],
        application=parameter['server']['application']
    )

    if parameter['wallbox']['active']:
        wallbox_token = get_secret('WALLBOX_TOKEN_FILE',
                                   os.environ.get('WALLBOX_TOKEN'))
        wallbox = Wattpilot(
            ip=parameter['wallbox']['host'],
            password=pw(wallbox_token, MOSQUITTO_CIPHER),
            auto_reconnect=True
        )
        wallbox.connect()

    z = FroniusToInflux(
        client=client,
        parameter=parameter,
        endpoints=endpoints,
        wallbox=wallbox,
        dry_run=parameter['dry_run']
    )
    z.ignore_sun_down = parameter['ignore_sun_down']
    z.run()


if __name__ == "__main__":
    main()
