#!/usr/bin/env python3

import json
import os
from enum import Enum
from pathlib import Path

WORKING_DIR = os.path.dirname(
    os.path.realpath(__file__)
)
OUTPUT_FILE = WORKING_DIR + "/data/secrets.json"
REFRESH_FILE = WORKING_DIR + "/hc_refresh_token.py"

BASE_URL = "https://api.home-connect.com/security/oauth/"
ASSET_URL = "https://api.home-connect.com/api/homeappliances"
TOKEN_URL = BASE_URL + "token"


def read_secrets() -> dict:
    try:
        with open(
                file=OUTPUT_FILE,
                mode="r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # return empty dict if file not found


def write_secrets(
        secrets: dict
) -> None:
    output = Path(OUTPUT_FILE)
    output.parent.mkdir(
        exist_ok=True,
        parents=True)  # create dir if not exists
    with open(
            file=output,
            mode="w+") as f:
        json.dump(
            secrets,
            f,
            ensure_ascii=False,
            default=str,
            indent=4)


def headers(
        access_token: str
) -> dict:
    return {
        "Authorization": "Bearer " + access_token,
        "accept": "application/vnd.bsh.sdk.v1+json",
        "Accept-Language": "de-DE",  # "en-US"
        "Content-Type": "application/vnd.bsh.sdk.v1+json"
    }


ProgramsEnum = Enum(
    "ProgramsEnum",
    read_secrets().get('dishwasher', {}).get('programs', {})
)
