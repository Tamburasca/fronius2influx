#!/usr/bin/env python3

import json
import os
from enum import Enum
from pathlib import Path

working_dir = os.path.dirname(os.path.realpath(__file__))
output_file = working_dir + "/data/secrets.json"
refresh_file = working_dir + "/hc_refresh_token.py"

base_url = "https://api.home-connect.com/security/oauth/"
asset_url = "https://api.home-connect.com/api/homeappliances"
token_url = base_url + "token"


def read_secrets() -> dict:
    try:
        with open(
                file=output_file,
                mode="r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # return empty dict if file not found


def write_secrets(secrets: dict) -> None:
    output = Path(output_file)
    output.parent.mkdir(exist_ok=True, parents=True)  # create dir if not exists
    with open(
            file=output,
            mode="w+") as f:
        json.dump(
            secrets,
            f,
            ensure_ascii=False,
            default=str,
            indent=4)


def headers(access_token) -> dict:
    return {
        "Authorization": "Bearer " + access_token,
        "accept": "application/vnd.bsh.sdk.v1+json",
        "Accept-Language": "de-DE",  # "en-US"
        "Content-Type": "application/vnd.bsh.sdk.v1+json"
    }


ProgramsEnum = Enum(
    "ProgramsEnum",
    read_secrets().get('Dishwasher', {}).get('programs', {})
)
