# Fronius-To-InfluxDB

Request data from Fronius inverter's Rest API and store it in the 
InfluxDB v2.7 for visualization in Grafana. This application collects the most basic 
Fronius inverter data serving for a basic setup. If your installation is 
more advanced, some extra work may be reqired, though. 

# Fronius Endpoints 
This application collects data from the following endpoints (Symo GEN24 6.0).
Adjust fronius host and path accordingly (see parameter.json)

    "http://<host ip>/<path>/GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=1".format(fronius_host, fronius_path)
    "http://<host ip>/<path>/GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0".format(fronius_host, fronius_path)
    "http://<host ip>/<path>/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0".format(fronius_host, fronius_path)

# Installation 
The current installation runs on a Raspberry Pi 4 B (with 4 GB RAM and a 64 GB SD)
inside a Docker infrastructure, comprising three containers. 
![Architecture](https://github.com/Tamburasca/fronius2influx/blob/ac097b18312802a4f70ee57b75e141a81a3d2ea3/pics/FroniusAPP.png)

    cd docker
    docker-compose build
    docker-compose up -d

Please create the token files inside 
[docker/data/secrets](https://github.com/Tamburasca/fronius2influx/blob/426322986a35a77106e53a78811118613b7ca29a/docker/data/secrets) 
appropriately. The tokens for read and write access to the influxDB are 
visible in the docker-compose logs after first initialization.

# Visualization
available via Grafana 
[dashboards](https://github.com/Tamburasca/fronius2influx/blob/833969887f417cd0a51fba7c583c9fab22594d61/docker/data/grafana/etc/grafana/provisioning/dashboards) 
and 
[influxDB flux](https://github.com/Tamburasca/fronius2influx/blob/833969887f417cd0a51fba7c583c9fab22594d61/docker/data/influxdb2/explorer). 

# Wallbox: Wattpilot
Thanks to [Watpilot](https://github.com/joscha82/wattpilot/tree/main?tab=readme-ov-file)
we implemented parts of their coding to account for monitoring also the wallbox.

# Caveat
The current [setup](https://github.com/Tamburasca/fronius2influx/blob/786517e091e8524b049d52de65e08ff9f0e4c716/src/data/parameter.json) considers photovoltaic modules on either side of the 
rooftop. For other cases, adjust the FLUX statements (in Grafana) appropriately, i.e.
the setup is not generic.