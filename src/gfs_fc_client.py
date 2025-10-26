#!/usr/bin/env python

"""
gfs_fc_client.py

extracts NCEP (NOAA) remote GFS grib2 file by multibyte range downloads
according to filter parameters set and stores to temp files in data directory
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from time import sleep

import requests
from bs4 import BeautifulSoup
from multiurl import download
from requests import Response, HTTPError

# internal
from src.gfs_fc_aux import DATA_DIR, STEPS

FC_TIMES = [0, 6, 12, 18]
COMMON = "{_url}/{_model}.{_yyyymmdd}/{_H}/atmos/"
SEMI_LAGRANGIAN_GRID = (COMMON
                        + "{_model}.t{_H}z.sfluxgrbf{_fc_hour}.{_extension}")
GLOBAL_LONGITUDE_LATITUDE_GRID = (COMMON
                                  + "{_model}.t{_H}z.{_params}{_set}.{_resol}.f{_fc_hour}")
PATTERN = {
    "SLS": SEMI_LAGRANGIAN_GRID,
    "GLOB": GLOBAL_LONGITUDE_LATITUDE_GRID
}
URLS = {
    "gfs": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod"
}


class Result:
    def __init__(
            self,
            rc,
            target
    ):
        self.target = target
        self.rc = rc


class Client(object):
    def __init__(
            self,
            *,
            grid,
            parameter=None,
#            validity=None,
            model="gfs",  # gdas, enkfgdas
            resol="0p25",  # SLS has a resolution of 360 / 1536 !
            paramset="",
            verify=True,
            **kwargs  # for date & time
    ):
        self.parameter = parameter if parameter else list()
        self.grid = grid
        self.model = model
        self.resol = resol
        self.paramset = paramset
        self.verify = verify
        self.session = requests.Session()
        self.target = "download.grib2"
        self.date = None
        self.time = None
        self.lower_by_fc = False

        # define base time at first and check availability
        self._dateandtime(**kwargs)
        # if neither date nor time is provided, we get last available fc
        # or one before otherwise
        if kwargs.get('date') is None and kwargs.get('time') is None:
            self._check_availability()

    def retrieve(
            self,
            *,
            step,
            **kwargs
    ):
        """
        download grib2 file...
        :param step:
        :param kwargs:
            target
        :return:
        """
        target = kwargs.get('target', self.target)

        # get m_url for multi-range download
        m_url = self._get_m_url(step=step)

        file = "{}{:03d}.grib2".format(
            target.split(".grib2")[0],
            step)

        if m_url:
            expected_size = sum([j[1] for j in m_url['parts']])
            # download byte multirange
            results = download(
                **m_url,
                target="{}/{}".format(DATA_DIR, file),
                verify=self.verify,
                session=self.session
            )
            # under Docker owner is root
            os.chmod("{}/{}".format(DATA_DIR, file), 0o666)
            return Result(
                rc=expected_size == results,
                target="{}/{}".format(DATA_DIR, file))
        else:
            logging.warning("No byte range provided with url. Skipping...")
            return Result(
                rc=False,
                target=None)

    @staticmethod
    def _get_url_paths(
            *,
            url: str,
            ext: str = ".idx",
            params=None  # ToDo: obsolete
    ) -> list | None:
        """
        returns list of all index files (full path) of the most recent fc
        :param url: url of COMMON
        :param ext: ".idx"
        :param params: not used
        :return:
        """
        response = requests.get(url, params=params)
        response.raise_for_status()
        if response.ok:
            soup = BeautifulSoup(response.text, 'html.parser')
            # list of all downloadable index files per weather forecast time
            return [url + node.get('href')
                    for node in soup.find_all('a')
                    if node.get('href').endswith(ext)]
        else:
            return None


    def _check_availability(self) -> None:
        """
        checks if all files for the most recent fc are available. If not, rerun
        dateandtime -6 hrs earlier
        :return: None
        """
        try:
            idx_list_available = self._get_url_paths(url=self._get_url())
            for step in STEPS:
                if self._get_url(step=step) + ".idx" not in idx_list_available:
                    raise LookupError
        except (HTTPError, LookupError):
            self.lower_by_fc = True
            logging.error("Files to be downloaded are not available..."
                          "trying a forecast 6 hrs. earlier.")
            self._dateandtime()

    def _dateandtime(
            self,
            **kwargs
    ) -> None:
        """
        set the time at [0|6|12|18] UTC before now. If lower_by_fc scale down
        by -6 hrs.
        :param kwargs:
        :return:
        """
        now = datetime.now(timezone.utc)
        time = int(now.strftime("%H"))

        if (kwargs.get('date')
                and (False if kwargs.get("time") in FC_TIMES else True)):
            kwargs['time'] = 18  # last fc time of the day
        else:
            kwargs['time'] = kwargs.get('time', time - time % 6)
        assert kwargs['time'] in FC_TIMES, "Value for time (UTC): [0|6|12|18]"
        kwargs['date'] = kwargs.get('date', now.strftime("%Y%m%d"))

        if self.lower_by_fc:
            dt = datetime.strptime(
                f"{kwargs['date']}{kwargs['time']}",
                "%Y%m%d%H"
            ) - timedelta(hours=6)  # one fc earlier
            self.date = dt.strftime("%Y%m%d")
            self.time = int(dt.strftime("%H"))
        else:
            self.date = kwargs['date']
            self.time = kwargs['time']

    def _get_url(
            self,
            step: int = None
    ) -> str:
        """
        prepare data and configure url string
        :param step:
        :return:
        """
        args = dict()

        args['_url'] = URLS['gfs']
        args['_model'] = self.model
        args['_extension'] = "grib2"
        # could be extended to e.g. goessimpgrb2 ???
        args['_params'] = "pgrb2"
        args['_set'] = self.paramset
        args['_resol'] = self.resol
        args['_yyyymmdd'] = self.date
        args['_H'] = "{:02d}".format(self.time)
        if step is None:
            return COMMON.format(**args)
        else:
            args['_fc_hour'] = "{:03d}".format(step)
            return PATTERN[self.grid].format(**args)

    def _get_m_url(
            self,
            step: int
    ) -> dict:
        """
        prepare data and configure url string
        :param step:
        :return:
        """
        try:
            idx = self._call_index(
                url=self._get_url(step=step)
            )
        except (Exception,) as e:
            logging.error(f"Error: {str(e)}, "
                          f"Resource not available. Revise your parameter set ...")
            return {}
        return self._prepare_request(idx)

    def _call_index(
            self,
            url: str
    ) -> dict[str, dict[int, dict]]:
        """
        extract the index files for offset and length of each parameter layer,
        can be filtered by shortName, level, and type.
        :param url:
        :return: index file in dict format
        """
        dix = dict()
        dict_keys = \
            ["offset", "datetime", "shortName", "level", "validity"]

        try:
            # total size of grib data file in bytes
            resp: Response = requests.get(url, stream=True)
            resp.raise_for_status()
            length = int(resp.headers.get("Content-length"))

            # download its appropriate index file
            url_index = f"{url}.idx"
            response = self.session.get(url_index)
            response.raise_for_status()
            dix[url] = dict()
            logging.info(f"Index file {str(url_index)} downloaded")
        except requests.exceptions.HTTPError as e:
            raise e  # return empty dict for current url

        for line in response.iter_lines():
            item = line.decode('utf-8').split(":")[:-1]
            no = int(item[0])

            # convert list to dict by merging lists, skip first element that
            # is number of parameter entry
            dix[url][no] = dict(zip(dict_keys, item[1:]))

            dix[url][no]['datetime'] = \
                dix[url][no]['datetime'].replace("d=", "")
            dix[url][no]['offset'] = int(dix[url][no]['offset'])
            # replace length by offset minus offset of last record
            if no > 1:
                dix[url][no - 1]['length'] = \
                    dix[url][no]['offset'] - dix[url][no - 1]['offset']
                dix[url][no]['length'] = length - dix[url][no]['offset']

        # Caveat:
        # NOMAD permits a rate limit of <120/minute to their site.
        # hits are considered to be head/listing commands as well as actual
        # data download attempts, i.e. every get http request
        # The block is temporary and typically lasts for 10 minutes
        # the system is automatically configured to blacklist an IP if it
        # continually hits the site over the threshold.
        # source: ncep.pmb.dataflow@noaa.gov (Brian)
        # Hence, configure the sleep argument accordingly!
        sleep(2.5)

        return dix

    def _prepare_request(
            self,
            idx: dict[str, dict[int, dict]]
    ) -> dict:
        """
        prepare data multirange downloads of single url, see
        https://github.com/ecmwf/multiurl
        :param idx:
        :return:
        """
        url_download = dict()

        for url, v in idx.items():
            t = tuple()
            # size of the entire grib2 file
            highest_id = sorted(v, key=lambda x: x, reverse=True)[0]
            size = v[highest_id]['offset'] + v[highest_id]['length']

            # download entire parameter set, not recommended
            if not self.parameter:
                url_download = {
                    "url": url,
                    "parts": ((0, size),)
                }
                continue

            # number of parameter is key, might consider number as viable key!
            for k, value in v.items():
                for p in self.parameter:  # parameter to be selected
                    predicate = False

                    # checks of parameters requested
                    assert p.get('shortName'), "shortName must not be empty!"
                    if p.get('validity'):
                        assert p.get('typeOfLevel'), \
                            "typeOfLevel must not be empty!"

                    # evaluate fields shortName is compared in lower case
                    if value['shortName'].lower() in p['shortName']:
                        if p.get('typeOfLevel'):  # if exists typOfLevel
                            if p.get('validity'):  # if exists validity
                                if p['typeOfLevel'] in value['level'] \
                                        and p['validity'] in value['validity']:
                                    predicate = True
                            else:
                                if p['typeOfLevel'] in value['level']:
                                    predicate = True
                        else:
                            predicate = True

                    # ToDo keep for a time being
                    # if predicate and self.validity:
                    #     if not any(i in value['validity']
                    #                for i in self.validity):
                    #         predicate = False
                    if predicate:
                        logging.info("{}:{}:{}:{}".format(
                            value['datetime'],
                            value['shortName'],
                            value['level'],
                            value['validity'])
                        )
                        t += ((value['offset'], value['length']),)

            # only if filtered but filter did apply,
            if t:
                # remove duplicates and sort according to offset, but
                # slow with big numbers
                t = tuple(sorted(set(t), key=t.index))
                url_download = {
                    "url": url,
                    "parts": t}
            else:
                logging.warning("No filter applied.")
            # end for loop item number each url
            # print("\n")
        # end for loop url

        return url_download
