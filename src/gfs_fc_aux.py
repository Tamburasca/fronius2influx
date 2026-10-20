import json
import os

# Logging Format
MYFORMAT: str = ("%(asctime)s :: %(levelname)s: %(filename)s - %(name)s - "
                 "%(lineno)s - %(funcName)s()\t%(message)s")

SOURCE_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = "{}/data".format(SOURCE_DIR)

config_file = "{}/parameter.json".format(DATA_DIR)
with open(config_file, "r") as config_handle:
    CONFIG = json.load(config_handle)

DATA_FILE = "{}/forecast_gfs.json".format(DATA_DIR)

STEPS = list(range(0, 121)) + list(range(123, 385, 3))  # 0 step is "anl"


def defined_kwargs(**kwargs) -> dict:
    return {k: v for k, v in kwargs.items() if v is not None}


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
