# set base image (host OS)
FROM python:3.12-slim

# set the working directory in the container
WORKDIR /Fronius/

# copy the content of the local src directory to the working directory
COPY src/fronius2influx.py src/
COPY src/fronius_aux.py src/
COPY src/fronius_ws_sync_client.py src/
COPY src/wattpilot*.py src/
COPY src/data/parameter.json src/data/
COPY src/requirements.txt src/
# for requesting Fronius endpoints
COPY src/HTTPrequest_v2.py src/
COPY src/wrapper.sh src/
RUN chmod +x src/wrapper.sh

# install dependencies
RUN pip install --upgrade pip && \
    pip install -r src/requirements.txt && \
    rm -f src/requirements.txt

ENV PYTHONPATH=.
# command to run on container start
# python [-u] forces the stdout and stderr streams to be unbuffered.
# ENTRYPOINT ["python3", "-u", "src/fronius2influx.py"]
# ENTRYPOINT ["python3", "-u", "src/HTTPrequest_v2.py"]
CMD src/wrapper.sh