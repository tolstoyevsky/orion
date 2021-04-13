#!/usr/bin/env python3
# Copyright 2013-2016 Evgeny Golyshev <eugulixes@gmail.com>
# Copyright 2019 Denis Gavrilyuk <karpa4o4@gmail.com>
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

"""Module containing the Orion RPC server. """

import os
import sys
from urllib.parse import urljoin

import tornado.web
from tornado.options import options
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote

from orion.settings import (
    CONTAINER_NAME,
    IMAGE_BASE_URL,
    IMAGE_FILENAME,
)
from orion.codes import (
    CHANGE_VNC_PASSWORD_FAILED,
    CONTAINER_ALREADY_EXIST,
    IMAGE_DOES_NOT_EXIST,
    IMAGE_STARTING_UNAVAILABLE,
)
from orion.engine import QEMUDocker
from orion.exceptions import (
    ConnectionTimeout,
    ContainerAlreadyExists,
    ContainerDoesNotExists,
    ImageDoesNotExist,
    ImageStartingUnavailable,
    SocketWaitStrTimeout,
)


class Orion(RPCServer):  # pylint: disable=abstract-method
    """The handler which allows to emulate a device and run an OS on it using QEMU. """

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

        self._qemu = None

    def _can_start(self):
        from users.models import Person  # pylint: disable=import-outside-toplevel,import-error

        try:
            Person.objects.get(user__pk=self.user_id)
        except Person.DoesNotExist as exc:
            raise ImageStartingUnavailable from exc

    async def _change_vnc_password(self, request):
        try:
            await self._qemu.set_random_vnc_password()
        except (ConnectionTimeout, ContainerDoesNotExists, SocketWaitStrTimeout, ):
            self._destroy()
            request.ret_error(CHANGE_VNC_PASSWORD_FAILED)

    def _destroy(self):
        self._qemu.kill()

    @staticmethod
    def _image_exist(image_id):
        from images.models import Image  # pylint: disable=import-outside-toplevel,import-error

        try:
            Image.objects.get(image_id=image_id)
        except Image.DoesNotExist as exc:
            raise ImageDoesNotExist from exc

    def destroy(self):
        self._destroy()

    @remote
    async def start(self, request, image_id):
        try:
            self._can_start()
        except ImageStartingUnavailable:
            request.ret_error(IMAGE_STARTING_UNAVAILABLE)

        try:
            self._image_exist(image_id)
        except ImageDoesNotExist:
            request.ret_error(IMAGE_DOES_NOT_EXIST)

        container_name = CONTAINER_NAME.format(image_id=image_id)
        self._qemu = QEMUDocker(container_name)

        image_filename = IMAGE_FILENAME.format(image_id=image_id)
        image_url = urljoin(IMAGE_BASE_URL, image_filename)

        env = {
            'IMAGE_URL': image_url,
            'ENABLE_VNC_PASSWORD': 'true',
            'MONITOR_PORT': self._qemu.monitor_port,
            'SERIAL_PORT': self._qemu.serial_port,
        }
        try:
            self._qemu.run(env)
        except ContainerAlreadyExists:
            request.ret_error(CONTAINER_ALREADY_EXIST)

        self.io_loop.add_callback(lambda: self._change_vnc_password(request))


class Application(tornado.web.Application):
    """The class of tornado application. """

    def __init__(self):
        handlers = [
            (r'/orion/token/' + TOKEN_PATTERN, Orion),
        ]
        super().__init__(handlers)


def main():
    """Starts a tornado application. """

    if os.getuid() != 0:
        sys.stderr.write('{} must run as root\n'.format(sys.argv[0]))
        sys.exit(1)

    options.parse_command_line()

    IOLoop().start(Application(), options.port)


if __name__ == "__main__":
    main()
