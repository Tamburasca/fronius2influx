#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
from time import sleep
from typing import Any, Dict, List
from astral import LocationInfo
# from astral.julian import julianday_to_juliancentury, julianday
from astral.sun import elevation, azimuth  # , eq_of_time
from influxdb_client import InfluxDBClient, WriteOptions
from requests import get
from requests.exceptions import ConnectionError
import math
import pytz
from sys import exit
import os
import logging
# internal imports
from fronius_aux import flatten_json, get_secret

__author__ = "Dr. Ralf Antonius Timmermann"
__copyright__ = ("Copyright (c) 2024, Dr. Ralf Antonius Timmermann "
                 "All rights reserved.")
__credits__ = ""
__license__ = "BSD-3"
__version__ = "0.1.0"
__maintainer__ = "Dr. Ralf Antonius Timmermann"
__email__ = "ralf.timmermann@gmx.de"
__status__ = "QA"


class WrongFroniusData(Exception):
    pass


class SunIsDown(Exception):
    pass


class DataCollectionError(Exception):
    pass


class FroniusToInflux:
    BACKOFF_INTERVAL = 5
    IGNORE_SUN_DOWN = False
    SOLAR_CONSTANT = 1_361  # W m⁻²
    A = 0.00014  # constant / m⁻¹

    def __init__(
            self,
            client: InfluxDBClient,
            parameter: Dict[Any, Any],
            endpoints: List[str],
            debug: bool = False
    ):
        self.client = client
        self.write = client.write_api(write_options=WriteOptions())
        self.endpoints = endpoints
        self.parameter = parameter
        self.location = LocationInfo(
            name=parameter['location']['city'],
            region=parameter['location']['region'],
            latitude=parameter['location']['latitude'],
            longitude=parameter['location']['longitude'],
            timezone=parameter['location']['timezone']
        )
        self.tz = pytz.timezone(parameter['location']['timezone'])
        self.data: Dict[Any, Any] = dict()
        self.debug = debug

    def get_float_or_zero(
            self,
            value: str
    ) -> float:
        try:
            internal_data: Dict[Any, Any] = self.data['Body']['Data']
        except KeyError:
            raise WrongFroniusData('Response structure is not healthy.')
        return 0. if 'Value' not in internal_data.get(value, {}) \
                     or internal_data.get(value, {}).get('Value') is None \
            else float(internal_data.get(value)['Value'])

    def translate_response(self) -> List[Dict]:
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

    def sun_parameter(self):
        altitude = self.parameter["location"]["altitude"]["value"]
        el = elevation(self.location.observer)
        # ToDo equation of time needed?
        # print(eq_of_time(
        #     juliancentury=julianday_to_juliancentury(
        #         julianday=julianday(at=datetime.datetime.utcnow())
        #     )
        # ))
        if el > 0:
            az = azimuth(self.location.observer)
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
            result: Dict[str, float | None] = {
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
                        pytz.utc
                    ).isoformat(
                        timespec='seconds'
                    ),
                    'fields': flatten_json(result)
                }
            ]
        else:
            if not self.IGNORE_SUN_DOWN:
                raise SunIsDown
            else:
                return []

    def run(self) -> None:
        flag_sun_is_down = False
        flag_connection = False
        flag_exception = False
        try:
            while True:
                try:
                    collected_data = []
                    for url in self.endpoints:
                        response = get(url)
                        self.data = response.json()
                        collected_data.extend(self.translate_response())
                    # add solar parameter
                    collected_data.extend(self.sun_parameter())
                    if self.debug:
                        print(collected_data)
                    else:
                        self.write.write(
                            bucket="Fronius",
                            org="Fronius",
                            record=collected_data,
                            write_precision='s'
                        )
                    flag_sun_is_down = False
                    flag_connection = False
                    flag_exception = False
                    sleep(self.BACKOFF_INTERVAL)
                except SunIsDown:
                    if not flag_sun_is_down:
                        logging.warning("Waiting for sun to rise ...")
                        flag_sun_is_down = True
                    sleep(60)
                except ConnectionError:
                    if not flag_connection:
                        logging.warning("Waiting for connection ...")
                        flag_connection = True
                    sleep(10)
                except Exception as e:
                    if not flag_exception:
                        logging.error("Exception: {}".format(e))
                        logging.warning("Waiting for exception to suspend ...")
                        flag_exception = True
                    self.data = {}
                    sleep(10)

        except KeyboardInterrupt:
            print("Finishing. Goodbye!")
            exit(0)


if __name__ == "__main__":
    with open('data/parameter.json', 'r') as f:
        parameter = json.load(f)

    # Logging Format
    MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - "
                     "%(lineno)s - %(funcName)s()\t%(message)s")
    LOGGING_LEVEL: str = "DEBUG" if parameter['debug'] else "INFO"
    logging.basicConfig(format=MYFORMAT,
                        level=getattr(logging, LOGGING_LEVEL),
                        datefmt="%Y-%m-%d %H:%M:%S")

    INFLUXDB_HOST = os.getenv('INFLUXDB_HOST',
                              parameter['influxdb']['host'])
    INFLUXDB_PORT = int(os.getenv('INFLUXDB_PORT',
                                  parameter['influxdb']['port']))
    INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')  # if run outside Docker
    influxdb_token_write = get_secret('INFLUXDB_TOKEN_FILE',
                                      INFLUXDB_TOKEN)

    client = InfluxDBClient(
        url="http://{0}:{1}".format(INFLUXDB_HOST,
                                    INFLUXDB_PORT),
        token=influxdb_token_write,
        org=parameter['influxdb']['organization'],
        verify_ssl=parameter['influxdb']['verify_ssl']
    )

    fronius_host = parameter['server']['host']
    fronius_path = parameter['server']['path']
    endpoints = [
        "http://{0}{1}GetInverterRealtimeData.cgi"
        "?Scope=Device&DataCollection=CommonInverterData&DeviceId=1"
        .format(fronius_host,
                fronius_path),
        # "http://{0}{1}GetInverterRealtimeData.cgi"
        # "?Scope=Device&DataCollection=3PInverterData&DeviceId=1"
        # .format(fronius_host,
        #         fronius_path),
        "http://{0}{1}GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0"
        .format(fronius_host,
                fronius_path),
        "http://{0}{1}GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0"
        .format(fronius_host,
                fronius_path)
    ]

    z = FroniusToInflux(
        client=client,
        parameter=parameter,
        endpoints=endpoints,
        debug=parameter['debug']
    )
    z.IGNORE_SUN_DOWN = parameter['ignore_sun_down']
    z.run()
