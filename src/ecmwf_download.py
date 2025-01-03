#!/usr/bin/env python

"""
ECMWF 10-day or 90-hr weather forecast for provided coordinates in
parameter.json. For public access - with no license - temporal and
spatiol resolution is downgraded. See specs.

ECMWF HRS
https://www.ecmwf.int/en/forecasts/datasets/set-i

ecmwf-opendata
https://github.com/ecmwf/ecmwf-opendata

pygrib docu
https://jswhit.github.io/pygrib/index.html
"""

import os
import sys
import argparse
import json
import math
import logging
from pygrib import open as pygrib_open
from numpy import array as np_array
from ecmwf.opendata import Client as ECMWFClient
from scipy.interpolate import RegularGridInterpolator
from datetime import datetime
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
# internal
from ecmwf_calculate import SunInflux
from fronius_aux import get_secret

# Logging Format
MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - %(name)s - "
                 "%(lineno)s - %(funcName)s()\t%(message)s")
SPATIAL_RESOLUTION: float = 0.25
# data directory relative to source
DATA_DIR = "{}/data".format(os.path.dirname(os.path.realpath(__file__)))


def create_grid(
        coordinates: np_array,
        resolution: float
) -> dict[str, float]:
    """
    create grid on coordinates
    :param coordinates:
    :param resolution:
    :return:
    """

    def transpose(x): return (x + 180) % 360 - 180  # [-180, 180[

    def floor(x): return math.floor(x / resolution) * resolution

    def ceil(x): return math.ceil(x / resolution) * resolution

    return {
        "lat1": max(-90, floor(coordinates[0])),
        "lat2": min(90, ceil(coordinates[0])),
        "lon1": transpose(floor(coordinates[1])),
        "lon2": transpose(ceil(coordinates[1]))
    }


def retrieve_ecmwf(
        params: list,
        steps: list,
        coords: np_array,
        grid: dict
) -> dict:

    file_default = "grib_tmp.grib2"
    dict_x: dict = {}
    target: str = "{}/{}".format(DATA_DIR, file_default)

    # loop over all parameter
    for param in params:
        client = ECMWFClient()
        results = client.retrieve(
            step=steps,
            type="fc",  # default
            param=param,
            # levelist=levelist,
            model="ifs",  # ifs for the physics-driven and aifs for the data-driven model
            resol="0p25",
            # preserve_request_order=True,  # ignored anyway
            target=target,
            # date='20241212',
            # time=00
        )
        os.chmod(target, 0o666)  # docker owner is root, anyone can delete
        logging.info(
            "Target file: {}\n"
            "Forecast Run (base time): {}"
            .format(results.target, results.datetime)
        )
        logging.debug("URLs requested: {}".format(results.urls))

        fsss = pygrib_open(target)
        fss = fsss.read()
        fsss.close()

        # loop over all available time steps
        for item in fss:
            logging.debug(item)
            data, lats, lons = item.data(**grid)
            nearest_neighbor = RegularGridInterpolator(
                (lats[:, 0], lons[0, :]),
                data,
                method='linear'
            )
            value_at_coordinates = list(nearest_neighbor(coords))[0]
            dt_str = "{}{:04d}".format(
                item['validityDate'],
                item['validityTime']
            )
            # create a global dict
            try:
                dict_x[item['name']]['time'].append(dt_str)
                dict_x[item['name']]['value'].append(value_at_coordinates)
            except KeyError:
                dict_x[item['name']] = {
                    "unit": item['units'],
                    "time": [dt_str],
                    "value": [value_at_coordinates]
                }

        if os.path.exists("{}/{}".format(DATA_DIR, file_default)):
            os.remove("{}/{}".format(DATA_DIR, file_default))
            logging.info("File '{}' deleted".format(file_default))

    logging.debug(
        json.dumps(
            dict_x,
            indent=2,
            sort_keys=True
        )
    )

    log_file = "{}/forecast.json".format(DATA_DIR)
    with open(log_file, "w") as jsonFile:
#        if os.getuid() == 0:  # chmod only if root
#            os.chmod(log_file, 0o666)  # docker owner is root, anyone can delete
        json.dump(dict_x,
                  jsonFile,
                  indent=2,
                  sort_keys=True)

    return dict_x


def main(
        extended: bool = False,
        test: bool = False
) -> None:

    # read configs
    config_file = "{}/parameter.json".format(DATA_DIR)
    config = json.load(open(config_file, "r"))

    # define logging
    logging_level: str = "DEBUG" if config['debug'] else "INFO"
    logging.basicConfig(format=MYFORMAT,
                        level=getattr(logging, logging_level),
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.info(f"Python version utilized: {sys.version_info}")
    # define influxDB client: write oken & synchronous load
    influxdb_host = os.getenv('INFLUXDB_HOST',
                              config['influxdb']['host'])
    influxdb_port = int(os.getenv('INFLUXDB_PORT',
                                  config['influxdb']['port']))
    # default applies, if runs outside Docker
    influxdb_token_write = get_secret('INFLUXDB_TOKEN_FILE',
                                      os.getenv('INFLUXDB_TOKEN'))
    influx_client = InfluxDBClient(
        url="http://{0}:{1}".format(influxdb_host,
                                    influxdb_port),
        token=influxdb_token_write,
        org=config['influxdb']['organization'],
        verify_ssl=config['influxdb']['verify_ssl']
    )
    influx_write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    # ECMWF open data parameters to be read subsequently
    params: list = config['ecmwf_forecast']['parameter']
    # Coordinates and its location in the grid
    coords = np_array([config['location']['latitude'],
                       config['location']['longitude']])
    # place a grid cell over the region to be used for forecast and interpolate
    grid: dict[str, float] = create_grid(coordinates=coords,
                                         resolution=SPATIAL_RESOLUTION)
    if extended:
        # HRES 	@ 00 and 12 hrs	UTC, step size: 0 to 144 by 3, 144 to 240 by 6
        steps: list = list(range(0, 144, 3)) + list(range(144, 241, 6))
        logging.info(
            "Fetching 10-day Forecast for parameter(s): {}".format(params))
    else:
        # HRES 	@ 06 and 18 hrs UTC, step size: 0 to 90 by 3
        steps: list = list(range(0, 91, 3))
        logging.info(
            "Fetching 90-hr Forecast for parameter(s): {}".format(params))

    dict_x = retrieve_ecmwf(
        params=params,
        steps=steps,
        coords=coords,
        grid=grid
    )

    z = SunInflux(
        parameter=config,
        debug=config['debug']
    )

    data = dict_x["Surface short-wave (solar) radiation downwards"]
    datum = [datetime.strptime(i, '%Y%m%d%H%M') for i in data['time']]
    values = [i for i in data['value']]
    records: list = list()

    csv_file_io = open("{}/solar_exp_power.csv".format(DATA_DIR), "w")
    csv_file_io.write(
        "{}, {}\n".format("date (UTC)", "expected solar energy (kWh)")
    )

    for i in range(len(datum) - 1):
        r1, r2 = z.calc(
            from_date=datum[i],
            to_date=datum[i+1]
        )
        # may be slightly negative by calculations of ECMWF (accumulated ssrd)!
        forecasted_flux = max(values[i + 1] - values[i], 0.)

        logging.debug(
            "Date: {}, "
            "Forecasted Flux [J m**-2]: {:.2E}, "
            "Max Flux [J m**-2]: {:.2E}, "
            "ratio: {:.3}, "
            "Energy on PV panels [kW]: {:.3}, "
            "Energy on PV panels corr. [kW]: {:.3}".format(
                datum[i],
                forecasted_flux,
                r1,
                r1 and forecasted_flux / r1 or 0.,
                r2,
                r2 * (r1 and forecasted_flux / r1 or 0.))
        )

        csv_file_io.write(
            "{}, {}\n".format(datum[i],
                              r2 * (r1 and forecasted_flux / r1 or 0.))
        )

        records.append(
            {
                "measurement": "Forecast",
                "time": datum[i],
                "fields": {"ssrd": r2 * (r1 and forecasted_flux / r1 or 0.)}
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

    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Downloads weather forecasts from ECMWF")
    parser.add_argument(
        '-e',
        '--extended',
        action="store_true",
        help="Fetch 10-day Forecast at 00 or 12 hrs, 90-hr Forecast (default)"
    )
    parser.add_argument(
        '-t',
        '--test',
        action="store_true",
        help="Test with no influxDB, write (default)"
    )

    main(
        extended=parser.parse_args().extended,
        test=parser.parse_args().test
    )
