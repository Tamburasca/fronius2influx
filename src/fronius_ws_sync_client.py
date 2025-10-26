#!/usr/bin/env python

"""
Client using the threading API.
"""
import json
import logging

from websockets import ConcurrencyError
from websockets.exceptions import ConnectionClosedError
from websockets.sync.client import connect

WEBSOCKET_PORT = 5000
WEBSOCKET_ENDPOINT = "/communicate"
URI = f"ws://localhost:{WEBSOCKET_PORT}{WEBSOCKET_ENDPOINT}"


class WSSyncClient:
    def __init__(self):
        self.websocket = None
        self.connected = True

    def _set_not_connected(self) -> None:
        if self.websocket:
            self.websocket.close()  # idempotent
            self.websocket = None  # may be obsolete
        self.connected = False

    def __call__(
            self,
            message: dict = None
    ) -> None:
        try:
            if not self.websocket:
                self.websocket = connect(URI)
            self.websocket.send(json.dumps(message))
            verify = self.websocket.recv()
            assert message == json.loads(verify), "Websocket message mismatch!"
            if not self.connected:
                logging.info(f"Reconnected to websocket Server ...")
                self.connected = True

        # when server never wasn't up yet
        except ConnectionRefusedError as e:
            if self.connected:
                logging.warning("ConnectionRefusedError: {}. {}".format(
                    e,
                    "Reconnecting to websocket Server ..."))
                self._set_not_connected()

        # after server was shut down and connection was established before
        except ConnectionClosedError as e:
            if self.connected:
                logging.warning("ConnectionClosedError: {}. {}".format(
                    e,
                    "Reconnecting to websocket Server ..."))
                self._set_not_connected()

        except ConcurrencyError as e:  # ToDo is applicable, as no two threads?
            if self.connected:
                logging.warning("ConcurrencyError: {}.".format(e))

        except AssertionError as e:
            logging.error("Error: {}".format(e))

        except OSError as e:
            logging.warning("OSError: {}. {}".format(
                e,
                "Reconnecting to websocket Server ..."))
            self._set_not_connected()

        except (Exception,) as e:
            logging.error("Unknown error: {}".format(e))
            self._set_not_connected()
