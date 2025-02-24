#!/usr/bin/env python

"""
gfs_fc_download.py

extract all parameters from temporary data files to dictionary
"""
import logging
import pygrib
import os
# import json
from numpy import array as np_array
from multiprocessing import Queue
from scipy.interpolate import RegularGridInterpolator
# internal
from gfs_fc_aux import CONFIG


# def write_forecast(
#         datetimestr: str,
#         forecast: dict
# ) -> None:
#     """
#     update forecast.json
#     :param datetimestr: YYYYMMDDHH
#     :param forecast:
#     :return: None
#     """
#     if not os.path.exists(DATA_FILE):
#         with open(DATA_FILE, "w") as create_empty:
#             json.dump({}, create_empty)
#             os.chmod(DATA_FILE, 0o666)  # docker owner is root, anyone can delete
#     with open(DATA_FILE, "r+") as jsonFile:
#         data = json.load(jsonFile)
#         data[datetimestr] = forecast
#         jsonFile.seek(0)  # rewind
#         json.dump(data,
#                   jsonFile,
#                   indent=2,
#                   sort_keys=True)
#         jsonFile.truncate()


def create_grid(
        coordinates: np_array,
        lats: np_array,
        lons: np_array
) -> dict:
    """
    create square in the coordinate grid that encloses location
    :param coordinates:
    :param lats:
    :param lons:
    :return:
    """
    lat1, lat2, lon1, lon2 = -90., 90., 0., 360.
    # lats scales from 90° to -90°
    for i in range(len(lats)):
        if coordinates[0] > lats[i]:
            lat1 = lats[i]
            break
        else:
            lat2 = lats[i]
    # longs scales from 0° to 360°  # for GFS, ECMWF ranges from -180° to 180°
    for i in range(len(lons)):
        if coordinates[1] < lons[i]:
            lon2 = lons[i]
            break
        else:
            lon1 = lons[i]

    return {
        "lat1": lat1,
        "lat2": lat2,
        "lon1": lon1,
        "lon2": lon2
    }


def extract(
        target: str,
        q: Queue = None,
        keep_target: bool = False
) -> tuple[bool, dict] | None:
    """
    extract grib2 file according to select parameter
    :param target: full path
    :param q: queue per fc hour for multiprocessing
    :param keep_target: keep target, if True
    :return:
    """
    fs: list = list()
    result: dict = dict()

    coords = np_array([CONFIG['location']['latitude'],
                       (CONFIG['location']['longitude'] + 360) % 360])

    # open grib file
    fsss = pygrib.open(target)
    # for i in fsss:
    #     print(i)
    #     for j in i.keys():
    #         print(j, getattr(i,j))
    fsss.seek(0)
    item = fsss.read(1)[0]
    # date of creation
    date_creation_str = "{}{:04d}".format(
        item['dataDate'],
        item['dataTime']
    )
    # figure out spatial resolution from 1st item
    resolution = 360 / item.values.shape[1]  # longitude
    logging.debug(f"Spatial resolution: {resolution} degree")
    lats, lons = item.latlons()
    # place a rectangle over the region to be used for forecast
    grid = create_grid(coordinates=coords,
                       lats=lats[:, 0],
                       lons=lons[0, :])

    fs.extend(fsss.select())
    fsss.close()

    for item in fs:
        print(item["shortName"], "->", item)
        data, lats, lons = item.data(**grid)
        nearest_neighbor = RegularGridInterpolator(
            (lats[:, 0], lons[0, :]),
            data,
            method='linear'
        )
        value_at_coordinates = list(nearest_neighbor(coords))[0]

        # key is somewhat crummy
        combined_dict_key = ("{}:{}:{}:{}"
                            .format(item['name'],
                                    item['typeOfLevel'],
                                    item['stepType'],
                                    item['level']))
        dt_str = "{}{:04d}".format(
            item['validityDate'],
            item['validityTime']
        )
        result[combined_dict_key] = {
            "unit": item['units'],
            "time": [dt_str],
            "value": [value_at_coordinates]
        }

    if not keep_target:
        os.remove(target)
        logging.debug("Target file '{}' deleted".format(target))

    if q:
        q.put((date_creation_str, result))
    else:
        return date_creation_str, result
