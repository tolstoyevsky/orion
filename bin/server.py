#!/usr/bin/env python3
# Copyright 2013-2016 Evgeny Golyshev <eugulixes@gmail.com>
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

import fcntl
import os
import pty
import shutil
import signal
import struct
import sys
import termios

import django
import docker
import psutil
import tornado.options
import tornado.web
from django.conf import settings
from pymongo import MongoClient
from shirow import util
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado import gen
from tornado.options import define, options

from firmwares.models import Firmware
from gits.terminal import Terminal
from users.models import User

IMAGE_DOES_NOT_EXIST = 1
IMAGE_IS_PREPARING = 2
IMAGE_COULD_NOT_BE_PREPARED = 3
IMAGE_TERMINATED = 4
IMAGE_IS_MISSING = 5

define('db_name',
       default=settings.MONGO['DATABASE'],
       help='')
define('dominion_workspace',
       default='/var/dominion/workspace/',
       help='')
define('mongodb_host',
       default=settings.MONGO['HOST'],
       help='')
define('mongodb_port',
       default=settings.MONGO['PORT'],
       help='')


class TermSocketHandler(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

        self._client = docker.APIClient(base_url='unix://var/run/docker.sock')

        self._image_internals_path = ''

        self._container_name = None
        self._fd = None
        self._script_p = None
        self._terminal = None

    def _init_mongodb(self):
        self.logger.debug(options.db_name)
        client = MongoClient(options.mongodb_host, options.mongodb_port)
        self.db = client[options.db_name]

    def destroy(self):
        if self._container_name:
            self._client.stop(self._container_name)

        if self._fd:
            self.io_loop.remove_handler(self._fd)
            try:
                self.logger.debug('Closing {}'.format(self._fd))
                os.close(self._fd)
            except OSError as e:
                self.logger.error('An error occured when attempting to '
                                  'close {}: {}'.format(self._fd, e))

        if self._script_p and self._script_p.status() == 'running':
            pid = self._script_p.pid
            try:
                self.logger.debug('Killing script process {}'.format(pid))
                os.kill(pid, signal.SIGKILL)
            except OSError as e:
                self.logger.error('An error occured when attempting to '
                                  'kill {}: {}'.format(pid, e))

        if os.path.isdir(self._image_internals_path):
            self.logger.debug('Removing image internals '
                              '{}'.format(self._image_internals_path))
            shutil.rmtree(self._image_internals_path)

    @remote
    def start(self, request, image_name, rows=24, cols=80):
        self._init_mongodb()
        user = User.objects.get(id=self.user_id)
        firmwares = Firmware.objects.filter(user=user) \
                                    .filter(status=Firmware.DONE) \
                                    .order_by('-started_at')
        missing_status = True
        for firmware in firmwares:
            if firmware.name == image_name:
                missing_status = False
        
        if (missing_status):
            request.ret(IMAGE_IS_MISSING)

        self._image_internals_path = '/tmp/{}'.format(image_name)

        image_full_path = '{}/{}.img.gz'.format(options.dominion_workspace,
                                                image_name)

        if not os.path.isfile(image_full_path):
            request.ret(IMAGE_DOES_NOT_EXIST)

        request.ret_and_continue(IMAGE_IS_PREPARING)

        self.logger.info('Uncompressing image {}'.format(image_name))

        ret, _, err = yield util.execute_async(
            ['uncompress_image.sh', image_name], {
                'DOMINION_WORKSPACE': options.dominion_workspace,
                'PATH': os.getenv('PATH'),
            }
        )

        if ret:
            self.logger.error('An error occurred when uncompressing the image '
                              'named {}: {}'.format(err, image_name))
            request.ret(IMAGE_COULD_NOT_BE_PREPARED)

        pid, fd = pty.fork()
        if pid == 0:  # child process
            os.chdir(self._image_internals_path)

            cmd = [
                'docker-qemu.sh',
                '-e IMAGE={}.img'.format(image_name),
                '-n', image_name,
            ]

            env = {
                'COLUMNS': str(cols),
                'LINES': str(rows),
                'PATH': os.environ['PATH'],
                'TERM': 'linux',
            }
            os.execvpe(cmd[0], cmd, env)
        else:  # parent process
            self.logger.debug('docker-qemu.sh started with pid {}'.format(pid))

            self._fd = fd
            self._script_p = psutil.Process(pid)
            self._terminal = Terminal(rows, cols)

            attempts_number = 60
            for i in range(attempts_number):
                try:
                    # Image name is also used as a container name
                    self._client.inspect_container(image_name)
                    break
                except docker.errors.NotFound:
                    yield gen.sleep(1)

            self._container_name = image_name

            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.ioctl(fd, termios.TIOCSWINSZ,
                        struct.pack('HHHH', rows, cols, 0, 0))

            def callback(*args, **kwargs):
                # There can be the Input/output error if the process was
                # terminated unexpectedly.
                try:
                    buf = os.read(self._fd, 65536)
                except OSError:
                    self.destroy()
                    request.ret(IMAGE_TERMINATED)

                html = self._terminal.generate_html(buf)
                request.ret_and_continue(html)

            self.io_loop.add_handler(self._fd, callback, self.io_loop.READ)

    @remote
    def enter(self, _request, data):
        try:
            os.write(self._fd, data.encode('utf8'))
        except (IOError, OSError):
            self.destroy()


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/orion/token/' + TOKEN_PATTERN, TermSocketHandler),
        ]
        tornado.web.Application.__init__(self, handlers)


def main():
    if os.getuid() != 0:
        sys.stderr.write('{} must run as root\n'.format(sys.argv[0]))
        sys.exit(1)

    django.setup()

    tornado.options.parse_command_line()

    IOLoop().start(Application(), options.port)


if __name__ == "__main__":
    main()
