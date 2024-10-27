The following files are required in this folder:

    influxdb_init_password - Password for initial user of database Username is defined in influxdb2.env

    influxdb_token_read - InfluxDB token for Read

    influxdb_token_write - InfluxDB token for Write

    wattpilot_token - Wattpilot token

Each file must only contain a single line with the password/token, 
with no additional linefeeds. Remove a successive linefeed from the token by:

    echo -e "token" | tr -d '\n' > filename