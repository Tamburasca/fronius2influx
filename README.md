# Monitoring for a Fronius Photovoltaic Installation

Request monitoring data from a Fronius photovoltaic inverter's Rest API and 
store it in an InfluxDB for visualization in Grafana. This application collects
the most basic Fronius inverter data serving for a basic setup. If your 
installation is much different or more advanced, some extra work may be reqired,
though. 

Furthermore, weather forecasts are downloaded from the
[European Centre for Medium-Range Weather Forecasts (ECMWF)]([https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS), 
i.e. the "Surface short-wave (solar) radiation downwards", in order to 
predict the (day-by-day) energy to be expected by the PV installation 
for the upcoming 10 days.

# Fronius Endpoints 
This application collects data from the following endpoints (Symo GEN24 6.0).
Adjust fronius host and path accordingly (see parameter.json)

    "http://<host-ip>/<path>/GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=1"
    "http://<host-ip>/<path>/GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0"
    "http://<host-ip>/<path>/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0"

# Installation 
The current installation runs on a Raspberry Pi 4 B (with 4 GB RAM and a 
64 GB SD card) inside a Docker infrastructure, comprising four containers. 
![Architecture](https://github.com/Tamburasca/fronius2influx/blob/main/pics/FroniusAPP_1.png)

    cd docker
    docker-compose build
    docker-compose up -d

Please create the token files inside 
[docker/data/secrets](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/secrets/README.md) 
appropriately. The tokens for read and write access to the influxDB are 
visible in the docker-compose logs after first initialization.

# Visualization
available via Grafana 
[dashboards](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/grafana/etc/grafana/provisioning/dashboards) 
and 
[influxDB flux](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/influxdb2/explorer). 

# Wallbox: Wattpilot
Thanks to [Wattpilot](https://github.com/joscha82/wattpilot)
we implemented parts of their coding to account for monitoring the wallbox.

# Caveat
The current [setup](https://github.com/Tamburasca/fronius2influx/blob/main/src/data/parameter.json) considers photovoltaic modules on either side of the 
rooftop. For other cases, adjust the FLUX statements (in Grafana) appropriately, i.e.
the setup is not generic.