# start fastAPI at port=5000
python3 -u src/HTTPrequest_v2.py &
# start fronius2influx.py
python3 -u src/fronius2influx.py &
# Wait for any process to exit
wait
# Exit with status of process that exited first
exit $?