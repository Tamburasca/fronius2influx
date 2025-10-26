#!/usr/bin/env python3

import json
import logging
import os
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from requests import get, HTTPError, Response, exceptions

# internal
from src.fronius_aux import get_secret
from src.sun_influx import SunInflux

# Logging Format
MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - %(name)s - "
                 "%(lineno)s - %(funcName)s()\t%(message)s")
SOURCE_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = "{}/data".format(SOURCE_DIR)
DATA_FILE = "{}/forecast.json".format(DATA_DIR)
config_file = "{}/parameter.json".format(DATA_DIR)
with open(config_file, "r") as config_handle:
    CONFIG = json.load(config_handle)

_DOMAIN = "https://api.open-meteo.com/"
_APPLICATION = "v1/forecast"
_QUERY_PARAMETER = ("?latitude={_latitude}"
                    "&longitude={_longitude}"
                    "&hourly={_parameter}"
                    "&timezone=GMT"
                    "&forecast_days={_forecast_horizon}"
                    "&past_days={_past_days}")

# for the time being
_PARAMETER = [
    "diffuse_radiation",  # average over past 1 hour
    "direct_radiation"
]


def main(
    test: bool = False
) -> None:
    """
    Donwload open-meteo forecast and convert to energy forecast utilizing the
    PV architecture
    :param test: disable influxDB writing if true
    :return:
    """
    # define logging
    logging_level: str = "DEBUG" if CONFIG['debug'] else "INFO"
    logging.basicConfig(format=MYFORMAT,
                        level=getattr(logging, logging_level),
                        datefmt="%Y-%m-%d %H:%M:%S")

    # define influxDB client: write token & synchronous load
    influxdb_host = os.getenv('INFLUXDB_HOST',
                              CONFIG['influxdb']['host'])
    influxdb_port = int(os.getenv('INFLUXDB_PORT',
                                  CONFIG['influxdb']['port']))
    # default applies, if runs outside Docker
    influxdb_token_write = get_secret('INFLUXDB_TOKEN_FILE',
                                      os.getenv('INFLUXDB_TOKEN'))
    influx_client = InfluxDBClient(
        url="http://{0}:{1}".format(influxdb_host,
                                    influxdb_port),
        token=influxdb_token_write,
        org=CONFIG['influxdb']['organization'],
        verify_ssl=CONFIG['influxdb']['verify_ssl']
    )
    influx_write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    url = _DOMAIN + _APPLICATION + _QUERY_PARAMETER
    args = dict()
    args['_latitude'] = CONFIG['location']['latitude']
    args['_longitude'] = CONFIG['location']['longitude']
    args['_parameter'] = ",".join(_PARAMETER)
    args['_forecast_horizon'] = 14  # days
    args['_past_days'] = 0  # days

    content: Response = None
    try:
        content = get(url.format(**args))
        content.raise_for_status()  # HTTP status
    except (HTTPError, exceptions.ReadTimeout) as e:
        logging.error(f"Error: {e}, {content.content()}")
        sys.exit(1)

    result = content.json()['hourly']
    dict_x: dict[str, list[str | float]] = {
        'time': result['time']
    }
    for item in _PARAMETER:
        dict_x[item] = result[item]

    with open(DATA_FILE, "w") as jsonFile:
        if os.getuid() == 0:  # chmod only if root
            os.chmod(DATA_FILE, 0o666)  # docker owner is root, anyone can delete
        json.dump(dict_x,
                  jsonFile,
                  indent=2,
                  sort_keys=True)

    z = SunInflux(
        parameter=CONFIG,
        debug=CONFIG['debug']
    )

    diffuse = dict_x['diffuse_radiation']
    direct = dict_x['direct_radiation']
    datum = [datetime.strptime(i, '%Y-%m-%dT%H:%M') for i in dict_x['time']]
    records = list()

    csv_file_io = open("{}/solar_exp_power.csv".format(DATA_DIR), "w")
    csv_file_io.write(
        "{}, {}, {}\n".format(
            "date (UTC)",
            "expected direct solar energy (kWh)",
            "expected diffuse solar energy (kWh)")
    )

    for i in range(len(datum) - 1):
        r1, r2, r3 = z.calc_modified(
            from_date=datum[i],
            to_date=datum[i + 1]
        )
        forecasted_flux = (max(direct[i + 1], 0.)  # average of last hour
                           * (datum[i + 1] - datum[i]) / timedelta(hours=1))
        forecasted_diffuse = (max(diffuse[i + 1], 0.)
                              * (datum[i + 1] - datum[i]) / timedelta(hours=1))

        logging.debug(
            "Date: {}, "
            "Forecasted Flux [W m**-2]: {:.2E}, "
            "Max Flux [W m**-2]: {:.2E}, "
            "ratio: {:.3}, "
            "Energy on PV panels [kW]: {:.3}, "
            "Energy on PV panels corr. [kW]: {:.3}, "
            "Diffuse Energy on PV panels [kW]: {:.3}"
            .format(
                datum[i + 1],
                forecasted_flux,
                r1,
                r1 and forecasted_flux / r1 or 0.,
                r2 / 1_000,
                r2 * (r1 and forecasted_flux / r1 or 0.) / 1_000,
                r3 * forecasted_diffuse / 1_000)
        )
        csv_file_io.write(
            "{}, {}, {}\n".format(
                datum[i + 1],
                r2 * (r1 and forecasted_flux / r1 or 0.) / 1_000,
                r3 * forecasted_diffuse / 1_000)
        )
        records.append(
            {
                "measurement": "Forecast",
                "time": datum[i + 1],
                "fields": {
                    "forecast":
                        (r2 * (r1 and forecasted_flux / r1 or 0.) +
                         r3 * forecasted_diffuse) / 1_000}
            }
        )
    # end for loop over date/time entries

    if not test:
        influx_write_api.write(
            bucket="Fronius",
            org="Fronius",
            record=records
        )

    influx_write_api.close()
    csv_file_io.close()

    logging.info(f"{os.path.basename(__file__)} exited.")
    sys.exit(0)


if __name__ == "__main__":
    # logging.info(f"Python version utilized: {sys.version_info}")
    parser = ArgumentParser(
        description="Downloads weather forecasts from open-meteo.com")
    parser.add_argument(
        '-t',
        '--test',
        action="store_true",
        help="Enable test modus"
    )

    main(test=parser.parse_args().test)
