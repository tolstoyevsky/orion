# Copyright 2021 Denis Gavrilyuk <karpa4o4@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Module contaning means for interacting with a remote sockets. """

import asyncio
import socket
from contextlib import asynccontextmanager

from orion.exceptions import SocketWaitStrTimeout
from orion.settings import TCP_CONNECTION_TIMEOUT
from orion.utils import wait_for_it


class Socket:
    """Implements the high-level interface for asynchronous communication with
    a remote TCP sockets. """

    OUTPUT_SIZE = 2048
    WAIT_STR_TIMEOUT = 10

    def __init__(self, port):
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    async def connect(self):
        """Connects to a remote socket. """

        await wait_for_it(self._port, TCP_CONNECTION_TIMEOUT)
        self._sock.connect(('', self._port))

    def close(self):
        """Closes a remote socket file descriptor. """

        self._sock.close()

    async def wait_and_close(self, wait_str):
        """Closes a remote socket connection after the ``wait_str`` appears
        in a remote socket output data. """

        for _ in range(self.WAIT_STR_TIMEOUT):
            if wait_str in self.output():
                self.close()
                break

            await asyncio.sleep(1)
        else:
            raise SocketWaitStrTimeout

    def output(self):
        """Receives output data from a remote socket. """

        output = self._sock.recv(self.OUTPUT_SIZE)
        return output.decode()

    def send(self, string):
        """Sends the ``string`` data to a remote socket. """

        self._sock.send(string.encode())


@asynccontextmanager
async def closing_socket(port, *, wait_str=None):
    """Asynchronous context manager that closes a remote socket connection upon completion
    of the block. """

    sock = Socket(port)
    await sock.connect()

    try:
        yield sock
    finally:
        if wait_str:
            await sock.wait_and_close(wait_str)
        else:
            sock.close()
