#!/bin/bash
set -e

influx auth create \
    --description "Read ${DOCKER_INFLUXDB_INIT_BUCKET}" \
    --org "${DOCKER_INFLUXDB_INIT_ORG}" \
    --read-bucket "${DOCKER_INFLUXDB_INIT_BUCKET_ID}"

influx auth create \
    --description "Write ${DOCKER_INFLUXDB_INIT_BUCKET}" \
    --org "${DOCKER_INFLUXDB_INIT_ORG}" \
    --write-bucket "${DOCKER_INFLUXDB_INIT_BUCKET_ID}"