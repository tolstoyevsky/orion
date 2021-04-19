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

"""Module containing class for translating normal socket traffic to WebSockets traffic. """

import logging
import os
import signal

import psutil
import websockify

from orion.utils import allocate_port


class WebSocketProxy:
    """Implements interface which allows connect to the VNC server using a WebSocket protocol. """

    def __init__(self, vnc_port):
        self.port = allocate_port()

        self._process = None
        self._vnc_port = vnc_port

        self.logger = logging.getLogger('tornado.application')

    def kill(self):
        """Kills the WebSocket proxy server process. """

        if self._process and self._process.is_running():
            pid = self._process.pid
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError as exc:
                self.logger.error('An error occurred when attempting to kill %s: %s', pid, exc)

    def run(self):
        """Runs the WebSocket proxy server connected to VNC server. """

        pid = os.fork()
        if pid:
            self._process = psutil.Process(pid)
        else:
            ws_proxy = websockify.WebSocketProxy(listen_port=self.port, target_port=self._vnc_port,
                                                 target_host='127.0.0.1')
            ws_proxy.start_server()
