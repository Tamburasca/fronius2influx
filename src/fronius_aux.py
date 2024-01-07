from typing import Dict, Any
import os


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
