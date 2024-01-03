# coding: utf-8
import datetime
import json
from time import sleep
from typing import Any, Dict, List

from astral import LocationInfo
# from astral.julian import julianday_to_juliancentury, julianday
from astral.sun import sun, elevation, azimuth  # , eq_of_time
from influxdb_client_3 import InfluxDBClient3
from requests import get
from requests.exceptions import ConnectionError
import math
import pytz


class WrongFroniusData(Exception):
    pass


class SunIsDown(Exception):
    pass


class DataCollectionError(Exception):
    pass


def flatten_json(y) -> Dict[str, Any]:
    """
    https://towardsdatascience.com/flattening-json-objects-in-python-f5343c794b10
    :param y: semi-structured JSON object
    :return: flattened JSON object
    """
    out: Dict[str, Any] = dict()

    def flatten(x, name='') -> Dict[str, Any]:
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


class FroniusToInflux:
    BACKOFF_INTERVAL = 5
    IGNORE_SUN_DOWN = False

    def __init__(
            self,
            client: InfluxDBClient3,
            parameter: Dict[Any, Any],
            endpoints: List[str],
    ):
        self.client = client
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
            else internal_data.get(value)['Value']

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
            storage_controller = self.data['Body']['Data']['Controller']
            return [
                {
                    'measurement': storage,
                    'time': timestamp,
                    'fields': {
                        'Current_DC': storage_controller.get('Current_DC', 0.),
                        'Enable': storage_controller.get('Enable', -1),
                        'StateOfCharge_Relative': storage_controller.get(
                            'StateOfCharge_Relative', -1),
                        'Status_BatteryCell': storage_controller.get(
                            'Status_BatteryCell', -1),
                        'Temperature_Cell': storage_controller.get(
                            'Temperature_Cell', -1),
                        'Voltage_DC': storage_controller.get('Voltage_DC', 0.)
                    }
                }
            ]
        elif collection is None and meter == "Smart Meter TS 65A-3":
            meter_data = self.data['Body']['Data']
            return [
                {
                    'measurement': meter,
                    'time': timestamp,
                    'fields': {
                        'Enable': meter_data.get(
                            'Enable', -1),
                        'PowerReal_P_Sum': meter_data.get(
                            'PowerReal_P_Sum', 0.),
                        'PowerReal_P_Phase_1': meter_data.get(
                            'PowerReal_P_Phase_1', 0.),
                        'PowerReal_P_Phase_2': meter_data.get(
                            'PowerReal_P_Phase_2', 0.),
                        'PowerReal_P_Phase_3': meter_data.get(
                            'PowerReal_P_Phase_3', 0.),
                        'Current_AC_Sum': meter_data.get(
                            'Current_AC_Sum', 0.),
                        'Current_AC_Phase_1': meter_data.get(
                            'Current_AC_Phase_1', 0.),
                        'Current_AC_Phase_2': meter_data.get(
                            'Current_AC_Phase_2', 0.),
                        'Current_AC_Phase_3': meter_data.get(
                            'Current_AC_Phase_3', 0.),
                        'Voltage_AC_Phase_1': meter_data.get(
                            'Voltage_AC_Phase_1', 0.),
                        'Voltage_AC_Phase_2': meter_data.get(
                            'Voltage_AC_Phase_2', 0.),
                        'Voltage_AC_Phase_3': meter_data.get(
                            'Voltage_AC_Phase_3', 0.),
                    }
                }
            ]
        else:
            print(collection, meter)
            raise DataCollectionError("Unknown data collection type.")

    def sun_is_shining(self) -> None:
        s = sun(
            self.location.observer,
            # date=datetime.datetime.now(tz=self.tz),
            tzinfo=self.tz
        )
        if (not self.IGNORE_SUN_DOWN
                and not s['sunrise']
                < datetime.datetime.now(tz=self.tz)
                < s['sunset']):
            raise SunIsDown
        return None

    def sun_parameter(self):
        a = 0.00014  # constant / m⁻¹
        altitude = self.parameter["location"]["altitude"]["value"]
        el = elevation(self.location.observer)
        az = azimuth(self.location.observer)
        # print(eq_of_time(
        #     juliancentury=julianday_to_juliancentury(
        #         julianday=julianday(at=datetime.datetime.utcnow())
        #     )
        # ))
        result: Dict[str, float | None] = dict()

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
            # https://www.pveducation.org/pvcdrom/properties-of-sunlight/air-mass#AMequation
            if el > 0:
                # air_mass = 1. / math.cos(math.radians(90. - el))
                air_mass_revised = 1. / (
                        math.cos(math.radians(90. - el))
                        + 0.50572 * (6.07995 + el) ** -1.6364
                )
                air_mass_attenuation = (
                        (1. - a * altitude) * 0.7 ** air_mass_revised ** 0.678
                        + a * altitude
                )
                # Direct beam intensity / W m⁻²
                intens = 1_353 * air_mass_attenuation
                # Estimate of global irradiance / W m⁻²
                # add_diffuse_radiation = 1.1 * intens
                print("{0}, "
                      "sun elevation: {7} deg, " 
                      "incidence angle: {1} deg, "
                      "incidence factor: {2}, "
                      "air mass: {3}, "
                      "air mass attenuation: {6}, "
                      "sun radiation: {4} Wm⁻², "
                      "true irradiation: {5} Wm⁻²".format(
                        item,
                        incidence_angle_sun,
                        r,
                        air_mass_revised,
                        intens,
                        intens * r,
                        air_mass_attenuation,
                        el))
                result[item] = {
                    "intensity_corr_area_eff": intens
                    * value['area']['value']
                    * value['efficiency']['value'],
                    "incidence_ratio": r
                }
            else:
                result[item] = {
                    "intensity_corr_area_eff": 0.,
                    "incidence_ratio": 0.
                }

        return [
            {
                'measurement': 'solar_data',
                'time': datetime.datetime.now(
                    pytz.utc
                ).isoformat(
                    timespec='seconds'
                ),
                'fields': flatten_json(result)
            }
        ]

    def run(self) -> None:
        try:
            while True:
                try:
                    self.sun_is_shining()
                    collected_data = []
                    for url in self.endpoints:
                        response = get(url)
                        self.data = response.json()
                        collected_data.extend(self.translate_response())
                        # sleep(self.BACKOFF_INTERVAL)
#                    self.client.write_points(collected_data)
                    # solar parameter
                    collected_data.extend(self.sun_parameter())
                    print(collected_data)
                    print('Data written')
                    sleep(self.BACKOFF_INTERVAL)
                except SunIsDown:
                    print("Waiting for sunrise")
                    sleep(60)
                    print('Waited 60 seconds for sunrise')
                except ConnectionError:
                    print("Waiting for connection...")
                    sleep(10)
                    print('Waited 10 seconds for connection')
                except Exception as e:
                    self.data = {}
                    sleep(10)
                    print("Exception: {}".format(e))

        except KeyboardInterrupt:
            print("Finishing. Goodbye!")


if __name__ == "__main__":

    with open('data/parameter.json', 'r') as f:
        parameter = json.load(f)

    fronius_host = parameter["server"]["host"]
    fronius_path = parameter["server"]["path"]

    client = InfluxDBClient3(
        host='localhost',
        port=8087,
        username='grafana',
        password='grafana',
        ssl=False
    )
    # client.switch_database('grafana')

    endpoints = [
        'http://{0}{1}GetInverterRealtimeData.cgi'
        '?Scope=Device&DataCollection=CommonInverterData&DeviceId=1'
        .format(fronius_host,
                fronius_path),
        'http://{0}{1}GetInverterRealtimeData.cgi'
        '?Scope=Device&DataCollection=3PInverterData&DeviceId=1'
        .format(fronius_host,
                fronius_path),
        'http://{0}{1}GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0'
        .format(fronius_host,
                fronius_path),
        'http://{0}{1}GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0'
        .format(fronius_host,
                fronius_path)
    ]

    z = FroniusToInflux(
        client=client,
        parameter=parameter,
        endpoints=endpoints
    )
    z.IGNORE_SUN_DOWN = True
    z.run()
