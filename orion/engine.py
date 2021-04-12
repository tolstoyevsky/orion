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

"""Module containing engines for running QEMU on different platforms. """

import docker
from docker.errors import APIError, NotFound

from orion import settings
from orion.exceptions import ContainerAlreadyExists
from orion.socket import closing_socket
from orion.utils import allocate_port, get_random_string

_DOCKER_CLIENT = docker.from_env()

DOCKER = _DOCKER_CLIENT.containers


class QEMUDocker:
    """The engine allows run QEMU in a docker container. """

    def __init__(self, container_name):
        self._container_name = container_name
        self._container = None

        self.monitor_port = allocate_port()
        self.vnc_password = get_random_string(8)

        self._run_kwargs = {
            'detach': True,
            'remove': True,
            'name': container_name,
            'privileged': True,
            'network': 'host',
            'volumes': {
                '/dev': {'bind': '/dev', 'mode': 'rw'},
            },
            'environment': {},
        }

    def kill(self):
        """Kills the QEMU container. The method does not raise any exception if the container
        either does not exist or is not running.
        """

        try:
            self._container.kill()
        except (APIError, NotFound, ):
            # Probably the container is not running. Simply ignore it.
            return None

        return None

    def run(self, env):
        """Runs the QEMU container, optionally passing environment variables to it via ``env``. """

        if env:
            self._run_kwargs['environment'].update(env)

        try:
            self._container = DOCKER.run(settings.QEMU_IMAGE, **self._run_kwargs)
        except APIError as exc:
            raise ContainerAlreadyExists from exc

    async def set_random_vnc_password(self):
        """Sets a random access password for the VNC session running in the QEMU container. """

        command = 'change vnc password'
        async with closing_socket(self.monitor_port, wait_str=command) as socket:
            socket.send(f'{command} {self.vnc_password}\n{self.vnc_password}\n')
