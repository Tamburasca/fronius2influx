#!/bin/bash

scriptPath=$(dirname "$(readlink -f "$0")")
source "${scriptPath}/.env.sh"

# Code of python:3.12-slim is located under /usr/local/bin/python3
/usr/local/bin/python3 /app/src/open-meteo2influx.py "$@"