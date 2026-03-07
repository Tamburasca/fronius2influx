#!/usr/bin/env python

"""
Client using the threading API.
"""
import json
import logging

from websockets import ConcurrencyError
from websockets.exceptions import ConnectionClosedError
from websockets.sync.client import connect, ClientConnection

WEBSOCKET_PORT = 5000
WEBSOCKET_ENDPOINT = "/communicate"
URI = f"ws://localhost:{WEBSOCKET_PORT}{WEBSOCKET_ENDPOINT}"


class WSSyncClient:
    def __init__(self):
        self.websocket: ClientConnection | None = None
        self.connected: bool = True
        self.msg_reconnecting: str = "Reconnecting to Websocket Server ..."

    def _set_not_connected(self) -> None:
        if self.websocket:
            self.websocket.close()  # idempotent
            self.websocket = None  # may be obsolete
        self.connected = False

    def __call__(
            self,
            message: list[dict]
    ) -> None:
        try:
            if not self.websocket:
                self.websocket = connect(URI)
                if self.connected:
                    logging.info(f"Connected to Websocket Server ...")
            if not self.connected:
                logging.info(f"Reconnected to Websocket Server ...")
                self.connected = True
            self.websocket.send(json.dumps(message))
            verify = self.websocket.recv()
            assert message == json.loads(verify), "Websocket message mismatch!"

        # when server never wasn't up yet
        except ConnectionRefusedError as e:
            if self.connected:
                logging.warning("ConnectionRefusedError: {}. {}".format(
                    e, self.msg_reconnecting))
                self._set_not_connected()

        # after server was shut down and connection was established before
        except ConnectionClosedError as e:
            if self.connected:
                logging.warning("ConnectionClosedError: {}. {}".format(
                    e, self.msg_reconnecting))
                self._set_not_connected()

        except ConcurrencyError as e:  # ToDo is applicable, as no two threads?
            if self.connected:
                logging.warning("ConcurrencyError: {}.".format(e))

        except AssertionError as e:
            logging.error("Error: {}".format(e))

        except OSError as e:
            logging.warning("OSError: {}. {}".format(
                e, self.msg_reconnecting))
            self._set_not_connected()

        except (Exception,) as e:
            logging.error("Unknown error: {}".format(e))
            self._set_not_connected()
