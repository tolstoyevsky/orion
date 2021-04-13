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

import tornado.web
from tornado.options import options
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote


class Orion(RPCServer):  # pylint: disable=abstract-method
    """The handler which allows to emulate a device and run an OS on it using QEMU. """

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)

    def destroy(self):
        pass

    @remote
    def start(self, request):
        pass


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
