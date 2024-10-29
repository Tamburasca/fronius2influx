# Fronius-To-InfluxDB

Request data from Fronius inverter's Rest API and store it in the 
InfluxDB v2.7 for visualization in Grafana. This application collects the most basic 
Fronius inverter data serving for a basic setup. If your installation is 
more advanced, some extra work may be reqired, though. 

# Fronius Endpoints 
This application collects data from the following endpoints (Symo GEN24 6.0).
Adjust fronius host and path accordingly (see parameter.json)

    "http://<host-ip>/<path>/GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=1"
    "http://<host-ip>/<path>/GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0"
    "http://<host-ip>/<path>/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0"

# Installation 
The current installation runs on a Raspberry Pi 4 B (with 4 GB RAM and a 64 GB SD)
inside a Docker infrastructure, comprising three containers. 
![Architecture](https://github.com/Tamburasca/fronius2influx/blob/main/pics/FroniusAPP.png)

    cd docker
    docker-compose build
    docker-compose up -d

Please create the token files inside 
[docker/data/secrets](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/secrets/README.md) 
appropriately. The tokens for read and write access to the influxDB are 
visible in the docker-compose logs after first initialization.

# Visualization
available via Grafana 
[dashboards](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/grafana/etc/grafana/provisioning) 
and 
[influxDB flux](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/influxdb2/explorer). 

# Wallbox: Wattpilot
Thanks to [Wattpilot](https://github.com/joscha82/wattpilot)
we implemented parts of their coding to account for monitoring the wallbox.

# Caveat
The current [setup](https://github.com/Tamburasca/fronius2influx/blob/main/src/data/parameter.json) considers photovoltaic modules on either side of the 
rooftop. For other cases, adjust the FLUX statements (in Grafana) appropriately, i.e.
the setup is not generic.