# set base image (host OS)
FROM python:3.13-slim

# set the working directory in the container
WORKDIR /Fronius/

# copy the content of the local src directory to the working directory
COPY src/fronius2influx.py src/fronius_*.py src/
COPY src/wattpilot*.py src/
COPY src/data/parameter.json src/data/
COPY src/requirements.txt src/

# Fronius RestAPI
COPY src/HTTPrequest_v2.py src/

COPY src/wrapper.sh src/
RUN chmod +x src/wrapper.sh

# install dependencies
RUN pip install --upgrade pip && \
    pip install -r src/requirements.txt && \
    rm -f src/requirements.txt

# cleansing
RUN apt-get -y autoremove && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONPATH=.
# command to run on container start
# python [-u] forces the stdout and stderr streams to be unbuffered.
# ENTRYPOINT ["python3", "-u", "src/fronius2influx.py"]
# ENTRYPOINT ["python3", "-u", "src/HTTPrequest_v2.py"]
CMD ["src/wrapper.sh"]