#!/usr/bin/env python

"""
Client using the threading API.
for a reading, see:
# https://websockets.readthedocs.io/en/stable/reference/sync/client.html
"""
import json
import logging

from websockets.exceptions import ConnectionClosedError
from websockets.sync.client import connect, ClientConnection


class WSSyncClient(object):
    def __init__(
            self,
            application: str,
            port: int
    ) -> None:
        """
        Transmits messages from fronius2influx to HTTP Rest API before it writes
        to the InfluxDB.
        :param application: application endpoint
        :param port: port of ws server
        """
        self.__uri = f"ws://localhost:{port}{application}"
        self.__ws: ClientConnection
        self.__connected: bool = False
        self.__msg_issued = False
        self.__msg_reconnecting: str = "Reconnecting to Websocket Server ..."

    def __call__(
            self,
            message: list[dict]
    ) -> None:
        """
        on every call transmit a message from fronius2influx to HTTP Rest API
        :param message: list of dict
        :return: None
        """
        try:
            if not self.__connected:
                self.__ws = connect(self.__uri, timeout=None)
                self._set_connected()
                logging.info(f"Connected to Websocket Server ...")
            self.__ws.send(json.dumps(message))
            verify = self.__ws.recv()
            assert message == json.loads(verify), "Websocket message mismatch!"

        # when server never wasn't up yet
        except ConnectionRefusedError as e:
            if not self.__msg_issued:
                logging.warning("ConnectionRefusedError: {}. {}".format(
                    e, self.__msg_reconnecting))
                self._set_not_connected()

        # after server was shut down and connection was established before
        except ConnectionClosedError as e:
            if not self.__msg_issued:
                logging.warning("ConnectionClosedError: {}. {}".format(
                    e,
                    self.__msg_reconnecting))
                self._set_not_connected()

        except AssertionError as e:
            logging.error("Error: {}".format(e))

        except OSError as e:
            logging.warning("OSError: {}. {}".format(
                e, self.__msg_reconnecting))
            self._set_not_connected()

        except (Exception,) as e:
            logging.error("Unknown error: {}".format(e))
            self._set_not_connected()

    def _set_not_connected(self) -> None:
        self.__ws.close()
        self.__connected = False
        self.__msg_issued = True

    def _set_connected(self) -> None:
        self.__connected = True
        self.__msg_issued = False
