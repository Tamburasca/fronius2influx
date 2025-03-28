#!/usr/bin/env python3

import os
from cryptography.fernet import Fernet


def flatten_json(y: dict) -> dict[str, any]:
    """
    https://towardsdatascience.com/flattening-json-objects-in-python-f5343c794b10
    :param y: semi-structured JSON object
    :return: flattened JSON object
    """
    out: dict[str, any] = dict()

    def flatten(x, name='') -> dict[str, any]:
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


def pw(
        pw_encoded: str,
        cipher: str
) -> str:
    """
    decrypts application key via cryptography.Fernet()
    :param pw_encoded: string
        encoded application key
    :param cipher: string
        decrypt key
    :return:
        str: decoded application key
    """
    if cipher is None:
        raise Exception("Please set the environment variable MOSQUITTO_CIPHER")
    return Fernet(str.encode(cipher)).decrypt(str.encode(pw_encoded)).decode()
