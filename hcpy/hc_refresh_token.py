#!/usr/bin/env python3

import datetime
import json
import logging
import time

import requests

# internal imports
from hc_aux import read_secrets, write_secrets, token_url


def refresh_token(
        t: int = 21_600,  # every 6 hrs.
) -> None:
    """
    refresh token
    caveat: access token were refreshed too often (only 100 refreshes are allowed per day and 10 per minute)

    :return: None
    """
    # fetch access token
    secrets = read_secrets()
    if not secrets:
        logging.error("Error: no secrets available. Start 'hc_login_start.py' first!")
        exit(1)

    while True:
        time.sleep(t)

        data = secrets["data"]
        secrets["timestamp"] = datetime.datetime.now().isoformat()

        refresh_token_fields = {
            "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
            "client_id": data["client_id"],
            "client_secret": data["client_secret"],
        }

        # Refreshing an Access Token
        r = requests.post(
            token_url,
            data=refresh_token_fields,
            allow_redirects=False,
            timeout=None,  # wait eternally
        )

        if r.status_code != requests.codes.ok:
            secrets["failed"] = True
            write_secrets(secrets)
            exit(1)

        data["refresh_token"] = json.loads(r.text)["refresh_token"]
        data["access_token"] = json.loads(r.text)["access_token"]
        secrets["failed"] = False
        write_secrets(secrets)


if __name__ == "__main__":
    refresh_token()
