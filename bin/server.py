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

import os
import sys

import tornado.options
import tornado.web
from tornado.options import options
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, TOKEN_PATTERN, remote


class TermSocketHandler(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

    def destroy(self):
        pass

    @remote
    def start(self, request):
        pass


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
