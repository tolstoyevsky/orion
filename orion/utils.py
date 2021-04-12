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

"""Module containing common code that might be shared between different modules. """

import asyncio
import random
import socket
import string

from orion.exceptions import ConnectionTimeout


def get_random_string(length):
    """Generates a random string with the length specified in the ``length``. """

    letters = string.ascii_lowercase
    return ''.join(random.choices(letters, k=length))


async def wait_for_it(port, timeout):
    """Waits on the availability of a host and TCP port. """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    for _ in range(timeout):
        try:
            sock.connect(('', port))
        except ConnectionRefusedError:
            await asyncio.sleep(1)
        else:
            sock.close()
            return

    raise ConnectionTimeout
