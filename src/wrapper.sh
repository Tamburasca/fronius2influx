# start fastAPI at port=5000
python3 -u src/HTTPrequest_v2.py &
# wait for websocket server to start
sleep 6
# start fronius2influx.py
python3 -u src/fronius2influx.py &
# Wait for any process to exit
wait
# Exit with status of process that exited first
exit $?