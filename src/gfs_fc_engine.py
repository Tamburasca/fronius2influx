#!/usr/bin/env python

"""
gfs_fc_engine.py

invokes the client (subsequently in order of forecast time) and executes the
extract module. Data in dictionary is stored into influxdb2 database.

Parallel mode permits to run the client and extract module in parallel
processing mode.
"""

import json
import logging
import os
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta
from multiprocessing import Process, Queue

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from fronius_aux import get_secret
from gfs_fc_aux import (defined_kwargs, CONFIG, STEPS, DATA_FILE, DATA_DIR,
                        MYFORMAT)
# internal
from gfs_fc_client import Client
from gfs_fc_download import extract
from sun_influx import SunInflux


def main(
        parallel: bool = False,
        keep_target: bool = False,
        test: bool = False
) -> None:
    """

    :param parallel: engage multiprocessing, if True
    :param keep_target: keep target, if True
    :param test: test modus, if True
    :return:
    """
    # define logging
    logging_level: str = "DEBUG" if CONFIG['debug'] else "INFO"
    logging.basicConfig(format=MYFORMAT,
                        level=getattr(logging, logging_level),
                        datefmt="%Y-%m-%d %H:%M:%S")

    # define influxDB client: write oken & synchronous load
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

    ps = list()  # list of processes
    qs = list()  # list of queues

    dict_x = dict()
    def collect(r: dict) -> dict:
        for k, v in r.items():
            try:
                dict_x[k]['time'].extend(v['time'])
                dict_x[k]['value'].extend(v['value'])
            except KeyError:
                dict_x[k] = v
        return dict_x
    # end module collect

    client = Client(
        # grid: mandatory [SLS|GLOB]
        grid= "SLS",
        # only used with grid="GLOB"
        paramset="",
        # only used with grid="GLOB"
        resol="0p25",
        **defined_kwargs(
            # if parameter missing, entire parameter set
            parameter=CONFIG.get('gfs_forecast'),
            # if missing, most recent date and/or time with data available
            date=CONFIG.get('date'),
            time=CONFIG.get('time')
        )
    )

    for step in CONFIG.get("steps", STEPS):
        results = client.retrieve(
            step=step,
            **defined_kwargs(
                target=CONFIG.get('target')
            )
        )
        # success, match file size(s)
        logging.info(f"File '{results.target}' size matched: {results.rc}")
        if not results.target:
            continue

        if parallel:
            queue = Queue()
            p = Process(target=extract,
                        args=(results.target, queue, keep_target),
                        daemon=True)
            # no join() required
            p.start()
            # renice on raspberry Pi
            os.system("renice -n 19 -p {} >/dev/null".format(p.pid))
            ps.append(p)
            qs.append(queue)
            logging.info("Number of alive processes: {}"
                  .format(sum([i.is_alive() for i in ps])))
        else:
            date_creation_string, res = extract(target=results.target)
            dict_x = collect(res)

    for q in qs:  # collecting from queue
        date_creation_string, res = q.get()
        dict_x = collect(res)

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

    data = dict_x["Downward short-wave radiation flux:surface:instant:0"]
    datum = [datetime.strptime(i, '%Y%m%d%H%M') for i in data['time']]
    values = [i for i in data['value']]
    records = list()

    csv_file_io = open("{}/solar_exp_power_gfs.csv".format(DATA_DIR), "w")
    csv_file_io.write(
        "{}, {}\n".format("date (UTC)", "expected solar energy (kWh)")
    )

    for i in range(len(datum) - 1):
        t = z.calc_modified(
            from_date=datum[i],
            to_date=datum[i + 1]
        )
        r1 = t[0] * 3_600  # convert W to J
        r2 = t[1] / 1_000  # convert to kWh
        # avarage adjecent neighbors and convert from Watt to Joule times
        # period of time in unit of hours
        forecasted_flux = ((values[i] + values[i + 1]) * 1800 *
                           (datum[i + 1] - datum[i]) / timedelta(hours=1))

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
                "fields": {"dswrf": r2 * (r1 and forecasted_flux / r1 or 0.)}
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
        description="Downloads weather forecasts from ECMWF")
    parser.add_argument(
        '-p',
        '--parallel',
        action="store_true",
        help="Apply Multiprocessing, if hardware permits the augmented load."
    )
    parser.add_argument(
        '-k',
        '--keep_target',
        action="store_true",
        help="Deletion of target files disabled."
    )
    parser.add_argument(
        '-t',
        '--test',
        action="store_true",
        help="Enable test modus"
    )

    main(
        parallel=parser.parse_args().parallel,
        keep_target=parser.parse_args().keep_target,
        test = parser.parse_args().test
    )
