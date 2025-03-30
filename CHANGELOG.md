# Changelog
## x.x.x (xxxx-xx-xx)
### Added
### Changed
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
