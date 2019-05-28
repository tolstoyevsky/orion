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

import fcntl
import os
import pty
import shutil
import signal
import struct
import sys
import termios

import docker
import psutil
import tornado.options
import tornado.web
from shirow import util
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado import gen
from tornado.options import define, options

IMAGE_DOES_NOT_EXIST = 1
IMAGE_IS_PREPARING = 2
IMAGE_COULD_NOT_BE_PREPARED = 3
IMAGE_TERMINATED = 4

define('dominion_workspace',
       default='/var/dominion/workspace/',
       help='')


class TermSocketHandler(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

        self._client = docker.APIClient(base_url='unix://var/run/docker.sock')

        self._image_internals_path = ''

        self._container_name = None
        self._fd = None
        self._script_p = None

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

                request.ret_and_continue(buf.decode('utf8', errors='replace'))

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

    tornado.options.parse_command_line()

    IOLoop().start(Application(), options.port)


if __name__ == "__main__":
    main()
