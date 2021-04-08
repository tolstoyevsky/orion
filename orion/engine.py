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
from docker.errors import APIError

from orion import settings
from orion.exceptions import ContainerAlreadyExists

_DOCKER_CLIENT = docker.from_env()

DOCKER = _DOCKER_CLIENT.containers


class QEMUDocker:
    """The engine allows run QEMU in a docker container. """

    def __init__(self, container_name):
        self._container_name = container_name
        self._container = None

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

    def run(self, env):
        """Runs the QEMU container, optionally passing environment variables to it via ``env``. """

        if env:
            self._run_kwargs['environment'].update(env)

        try:
            self._container = DOCKER.run(settings.QEMU_IMAGE, **self._run_kwargs)
        except APIError as exc:
            raise ContainerAlreadyExists from exc
