#!/usr/bin/env python

"""
Client using the threading API.
"""
import json
import logging

from websockets import ConcurrencyError
from websockets.exceptions import ConnectionClosedError
from websockets.sync.client import connect, ClientConnection


class WSSyncClient(object):
    def __init__(
            self,
            application: str,
            port: int
    ) -> None:
        self.application = application
        self.port = port
        self.__uri = f"ws://localhost:{port}{application}"
        self.__websocket: ClientConnection | None = None
        self.__connected: bool = True
        self.__msg_reconnecting: str = "Reconnecting to Websocket Server ..."

    def _set_not_connected(self) -> None:
        if self.__websocket:
            self.__websocket.close()  # idempotent
            self.__websocket = None  # may be obsolete
        self.__connected = False

    def __call__(
            self,
            message: list[dict]
    ) -> None:
        try:
            if not self.__websocket:
                self.__websocket = connect(self.__uri)
                if self.__connected:
                    logging.info(f"Connected to Websocket Server ...")
            if not self.__connected:
                logging.info(f"Reconnected to Websocket Server ...")
                self.__connected = True
            self.__websocket.send(json.dumps(message))
            verify = self.__websocket.recv()
            assert message == json.loads(verify), "Websocket message mismatch!"

        # when server never wasn't up yet
        except ConnectionRefusedError as e:
            if self.__connected:
                logging.warning("ConnectionRefusedError: {}. {}".format(
                    e, self.__msg_reconnecting))
                self._set_not_connected()

        # after server was shut down and connection was established before
        except ConnectionClosedError as e:
            if self.__connected:
                logging.warning("ConnectionClosedError: {}. {}".format(
                    e, self.__msg_reconnecting))
                self._set_not_connected()

        except ConcurrencyError as e:  # ToDo is applicable, as no two threads?
            if self.__connected:
                logging.warning("ConcurrencyError: {}.".format(e))

        except AssertionError as e:
            logging.error("Error: {}".format(e))

        except OSError as e:
            logging.warning("OSError: {}. {}".format(
                e, self.__msg_reconnecting))
            self._set_not_connected()

        except (Exception,) as e:
            logging.error("Unknown error: {}".format(e))
            self._set_not_connected()
