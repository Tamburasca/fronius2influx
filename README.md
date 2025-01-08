# Monitoring a PV Infrastructure by Fronius

Request monitoring data from a Fronius PV inverter's Rest API foreward and 
store it in an InfluxDB for visualization in Grafana. The current application 
collects the most fundamental Fronius inverter data serving for a basic setup. 
If your 
installation is much different or more advanced, some extra work may be reqired,
though.

Furthermore, weather forecasts, i.e. the "Surface short-wave (solar) radiation 
downwards", are downloaded from the
[European Centre for Medium-Range Weather Forecasts (ECMWF)]([https://confluence.ecmwf.int/display/DAC/ECMWF+open+data%3A+real-time+forecasts+from+IFS+and+AIFS), 
in order to predict the (day-by-day) energy to be expected by the PV installation 
for the upcoming 10 days.

# Fronius Endpoints 
This application collects data from the following endpoints (Symo GEN24 6.0).
For further reading see the appropriate
[API](https://www.fronius.com/~/downloads/Solar%20Energy/Operating%20Instructions/42,0410,2012.pdf).
Adjust fronius host and path accordingly (see 
[parameter.json](https://github.com/Tamburasca/fronius2influx/blob/main/src/data/parameter.json))

    "http://<host-ip>/<path>/GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=1"
    "http://<host-ip>/<path>/GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0"
    "http://<host-ip>/<path>/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0"

# influxDB
All data is stored in bucket "Fronius", comprising the following measurements:

* "DeviceStatus": status of inverter (no dashboard available in Grafana).
* "CommonInverterData": values which are cumulated to generate a system overview
* "Battery": charging status, (dis-)charging demand (voltage and current), temperature
* "SmartMeter": detailed information about Meter devices.
* "SolarData": calculated energy on each panel, as function of the geolocation of PV installation, solar position, and attenuation owing to airmass  
* "Forecast": predicted solar flux (units of kWh) on all PV panels 
as cumulated over the step size provided by ECMWF for the next 10 days.
ECMWF data is updated 4 times a day - according to the cron job in docker.

Moreover, in bucket "aggregates" the measurement "daily" represents a 
materialized view over all energy data as downsampled to 1 minute. 
The dashboards "Aggregates Daily and Monthly" query on this measurement. The 
[task](https://github.com/Tamburasca/fronius2influx/blob/main/docker/data/influxdb2/explorer/downsample.flux) for the creation of the 
materialized view runs once a day triggered by an influxDB scheduler.

# Architecture 
The current installation runs on a Raspberry Pi 4 B (with 4 GB RAM and a 
64 GB SD card) inside a Docker infrastructure, comprising four containers. 
![Architecture](https://github.com/Tamburasca/fronius2influx/blob/main/pics/FroniusAPP_1.png)

    cd docker
    docker-compose build
    docker-compose up -d

Please create the token files inside [docker/data/secrets](https://github.com/Tamburasca/fronius2influx/tree/main/docker/data/secrets/README.md) 
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
The current setup 
considers photovoltaic modules on either side of the rooftop. 
For other cases, adjust the FLUX statements (in Grafana) appropriately, i.e.
the setup is not generic.

# Note
Current README will be updated in more detail.