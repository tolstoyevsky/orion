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
import signal
import struct
import sys
import termios

import tornado.options
import tornado.web
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote
from tornado.options import define, options

from gits.terminal import Terminal


class TermSocketHandler(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

        self._fd = self._pid = self._terminal = None

    def destroy(self):
        self.logger.info('closed')
        self.io_loop.remove_handler(self._fd)
        try:
            os.kill(self._pid, signal.SIGHUP)
            os.close(self._fd)
        except OSError:
            pass

    @remote
    def start(self, request, rows=24, cols=80):
        pid, fd = pty.fork()
        if pid == 0:
            cmd = ['/bin/login']

            env = {
                'COLUMNS': str(cols),
                'LINES': str(rows),
                'PATH': os.environ['PATH'],
                'TERM': 'linux',
            }
            os.execvpe(cmd[0], cmd, env)
        else:
            self._fd = fd
            self._pid = pid
            self._terminal = Terminal(rows, cols)

            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            fcntl.ioctl(fd, termios.TIOCSWINSZ,
                        struct.pack('HHHH', rows, cols, 0, 0))

            def callback(*args, **kwargs):
                buf = os.read(self._fd, 65536)
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

    tornado.options.parse_command_line()

    IOLoop().start(Application(), options.port)


if __name__ == "__main__":
    main()
