#!/usr/bin/env python3

# This directly follows the OAuth login flow that is opaquely described
# https://github.com/openid/AppAuth-Android
# A really nice walk through of how it works is:
# https://auth0.com/docs/get-started/authentication-and-authorization-flow/call-your-api-using-the-authorization-code-flow-with-pkce

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from base64 import urlsafe_b64encode as base64url_encode
from urllib.parse import unquote, urlencode

import requests
from Crypto.Random import get_random_bytes

# internal imports
from hc_aux import (read_secrets, write_secrets, output_file, refresh_file,
                    base_url, token_url, asset_url, headers)

# scopes used by the Home Connect app
scope = [
    "Dishwasher",
    "IdentifyAppliance",
    "Settings"
]


def b64(b):
    return re.sub(r"=", "", base64url_encode(b).decode("UTF-8"))


def b64random(num):
    return b64(base64url_encode(get_random_bytes(num)))


def login_page(
        client_id: str
) -> str:
    """

    :param client_id:
    :return:
    """
    login_query = {
        "response_type": "code",
        "prompt": "login",
        "code_challenge_method": "S256",
        "client_id": client_id,
        "scope": " ".join(scope),
        "state": b64random(16),
    }

    loginpage_url = base_url + "authorize?" + urlencode(login_query)

    print(
        "Visit the following URL in Chrome/Firefox,\n "
        "use the F12 developer tools "
        "to monitor the network responses, and look for the request starting "
        "https://apiclient.home-connect.com/o2c.html?code=<code> "
        "for the relevant authentication token:\n"
    )
    print(loginpage_url)

    return unquote(
        input("Input code: "))


def access_token_request(
        client_id: str,
        client_secret: str,
        code: str
) -> dict:
    """

    :param client_id:
    :param client_secret:
    :param code:
    :return:
    """
    token_fields = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }

    r = requests.post(
        token_url,
        data=token_fields,
        allow_redirects=False)
    if r.status_code != requests.codes.ok:
        print("Bad code?", file=sys.stderr)
        print(dict(r.headers), r.text)

        exit(1)

    secrets = {
        "data": {
            "client_id": client_id,
            "client_secret": client_secret,
            "access_token": json.loads(r.text)['access_token'],
            "refresh_token": json.loads(r.text)['refresh_token']
        },
        "timestamp": datetime.datetime.now().isoformat(),
        "failed": False,
    }

    return secrets


def get_haid(
        secrets: dict
) -> dict:
    """

    :param secrets:
    :return:
    """
    r = requests.get(
        asset_url,
        headers=headers(access_token=secrets['data']['access_token'])
    )
    if r.status_code != requests.codes.ok:
        print("Bad access token?", file=sys.stderr)
        print(dict(r.headers), r.text)

        exit(1)

    devices = json.loads(r.text)['data']['homeappliances']
    for item in devices:
        if (item.get("type") == "Dishwasher"
                and item.get("brand") == "Bosch"):
            secrets['timestamp'] = datetime.datetime.now().isoformat()
            secrets['Dishwasher'] = {}
            secrets['Dishwasher']['haId'] = item.get("haId")

    return secrets


def get_programs(
        secrets: dict
) -> dict:
    """

    :param secrets:
    :return:
    """
    en: dict = {}
    app_id = secrets['Dishwasher']['haId']

    # see here for an overview
    # https://github.com/jeroenvdwaal/home-connect-api
    r = requests.get(
        asset_url + "/" + app_id + "/programs",
        headers=headers(access_token=secrets['data']['access_token'])
    )
    if r.status_code != requests.codes.ok:
        print("Bad access token or haId?", file=sys.stderr)
        print(dict(r.headers), r.text)

        exit(1)

    programs_available = json.loads(r.text)['data']['programs']
    for items in programs_available:
        en[items['key']] = items['name']
    secrets['timestamp'] = datetime.datetime.now().isoformat()
    secrets['Dishwasher']['programs'] = en

    return secrets


def main() -> None:
    """
    get access token and refresh token & appliance ID and available programs
    :return:
    """
    argparser = argparse.ArgumentParser(
        description="HomeConnect Login Procedure")

    argparser.add_argument(
        '--client_id',
        required=False,
        type=str,
        help="Client ID (optional, if data exists)",
    )
    argparser.add_argument(
        '--client_secret',
        required=False,
        type=str,
        help="Client Secret (optional, if data exists)"
    )
    client_id = argparser.parse_args().client_id
    client_secret = argparser.parse_args().client_secret

    if client_id and client_secret:
        # supersede secrets
        secrets = access_token_request(
            client_id=client_id,
            client_secret=client_secret,
            code=login_page(
                client_id=client_id))
    else:
        secrets = read_secrets()
        if not secrets:
            print(
                "Error: HomeConnect credentials not available.",
                file=sys.stderr)
            exit(1)
        elif secrets['failed']:
            print(
                "Error: rerun the authorization process and provide the code.",
                file=sys.stderr)
            exit(1)

    # get appliance ID
    write_secrets(
        get_haid(secrets=secrets))

    # get available programs
    write_secrets(
        get_programs(secrets=secrets))

    if os.getuid() == 0:  # chmod only if root
        os.chmod(output_file, 0o666)  # docker owner is root, now anyone can edit/delete

    # spawn "refresh token" subprocess and exit
    process = subprocess.Popen(
        ["python3", refresh_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        start_new_session=True
    )
    print(f"Spawned PID: {process.pid}")

    exit(0)


if __name__ == "__main__":
    main()
