# Changelog
## x.x.x (xxxx-xx-xx)
### Added
### Changed
### Fixed
### Deprecated
### Removed
### Security
## 1.7.1 (2025-10-19)
### Added
### Changed
- architecture pic
- README.md
### Fixed
### Deprecated
### Removed
### Security
## 1.7.0 (2025-10-10)
### Added
### Changed
- Forecast logs to one single logfile only
- Docker logs for all services limited in size
### Fixed
- Error correction for HTTPrequest (StatusErrors added 1175)
- Error handling in wattpilot.py: reconnect on error after reconnection_interval 
and suppress error messages in log file
- pygrib imported from source and introduced a hotfix 
"from ctypes import c_long as long"
in _pygrib.pyx until pygrib is fixed in a future release
### Deprecated
### Removed
### Security
## 1.6.2 (2025-05-17)
### Added
### Changed
### Fixed
- Error correction for HTTPrequest 
- ASGImiddleware
### Deprecated
### Removed
### Security
## 1.6.1 (2025-05-15)
### Added
### Changed
### Fixed
- Error correction for HTTPrequest catch KeyError
- Catch OSError in websocket client
### Deprecated
### Removed
### Security
## 1.6.0 (2025-05-14)
### Added
### Changed
- WebSocket connection between fronius2influx and HTTPrequest
### Fixed
### Deprecated
### Removed
### Security
## 1.5.0 (2025-04-24)
### Added
- Additional endpoint in http Rest API for querying status of all devices
### Changed
- Additional field in "Smart meter" measurement in influxDB
### Fixed
- Error treatment minor changes
### Deprecated
### Removed
### Security
## 1.4.0 (2025-04-11)
### Added
- HTTP RestAPI to read the Fronius inverted directly (runs with 
fronius2influx.py in one docker container)
### Changed
### Fixed
### Deprecated
### Removed
- Async version of fronius2influx.py (slower than sync version)
### Security
## 1.3.0 (2025-04-10)
### Added
- forecast provided by open-meteo
### Changed
- solar flux added diffuse radiation (sun_influx.py)
### Fixed
### Deprecated
### Removed
### Security
## 1.2.0 (2025-03-27)
### Added
- Async version of Fronius readout, where the client InfluxDBClientAsync is
utilized. Turns out at least 2 times slower than the Sync version.
### Changed
- Data is cached and written to influxDB after WRITE_CYCLE=n cycles in order 
to reduce SD card write cycles.
### Fixed
### Deprecated
### Removed
### Security
## 1.1.0 (2025-02-24)
### Added
Energy prediction for the PV installation augmented
by utilizing the GFS weather forecast of NCEP (NOAA)
### Changed
### Fixed
### Deprecated
### Removed
### Security
## 1.0.1 (2025-01-12)
### Added
### Changed
- Class SunInflux calculation optimized for varying intervals
### Fixed
### Deprecated
### Removed
### Security
## 1.0.0 (2025-01-01)
### Added
- Energy prediction for the PV installation 
as computed utilizing the ECMWF weather forecast (open data)
### Changed
### Fixed
### Deprecated
### Removed
### Security
## 0.2.1 (2024-12-16)
### Added
### Changed
### Fixed
- Atmosphere's refraction considered
### Deprecated
### Removed
### Security
## 0.2.0 (2024-10-27)
### Added
- Wallbox - Wattpilot implented for writing to influxdb
### Changed
### Fixed
### Deprecated
### Removed
### Security
## 0.1.1 (2024-09-25)
### Added
### Changed
- Flux statements for InsertedPower panel in PowerLive dashboard (got faster!)
- Minor corrections to python code
- client.write_api(...) flush scheduler to 1 sec (default)
- typing
- requirements updated
- hack on Enum 
### Fixed
### Deprecated
### Removed
### Security
## 0.1.0 (2024-01-29)
### Added
- Flux statements for Grafana
### Changed
- Solar data (influxdb measurement) disabled if sun is down
### Fixed
### Deprecated
### Removed
### Security
## 0.0.2 (2024-01-22)
### Added
- debug flag, if enabled no writing to influxdb
### Changed
### Fixed
### Deprecated
### Removed
- 3PInverterData endpoint
### Security
## 0.0.1 (2024-01-07)
- initial commit
