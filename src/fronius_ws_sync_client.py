#!/usr/bin/env python

"""
Client using the threading API.
"""
import json
import logging
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosedError


WEBSOCKTET_PORT = 5000
WEBSOCKET_ENDPOINT = "/communicate"
URI = f"ws://localhost:{WEBSOCKTET_PORT}{WEBSOCKET_ENDPOINT}"


class WSSyncClient:
    def __init__(self):
        self.websocket = None
        self.connected = True

    def __call__(
            self,
            message: dict = None
    ) -> None:
        try:
            if not self.websocket: self.websocket = connect(URI)
            self.websocket.send(json.dumps(message))
            verify = self.websocket.recv()
            assert message == json.loads(verify), "Websocket message mismatch!"
            if not self.connected:
                logging.info(f"Reconnected to websocket Server ...")
                self.connected = True
        # ToDo yet to sort out which exception is called at which situation
        # when server never wasn't up yet
        except ConnectionRefusedError as e:
            if self.connected:
                logging.warning("ConnectionRefusedError: {}. {}".format(
                    e, "Reconnecting to websocket Server ..."))
                self.websocket = None
                self.connected = False
        # after server was shut down and connection was established before
        except ConnectionClosedError as e:
            if self.connected:
                logging.warning("ConnectionClosedError: {}. {}".format(
                    e, "Reconnecting to websocket Server ..."))
                self.websocket = None
                self.connected = False
        except AssertionError as e:
            logging.error("Error: {}".format(e))
        except (Exception,) as e:
            logging.error("Unknown error: {}".format(e))
