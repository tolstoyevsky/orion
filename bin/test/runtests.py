import jwt
import redis
from shirow.server import TOKEN_PATTERN
from tornado import gen
from tornado.concurrent import Future
from tornado.escape import json_decode, json_encode
from tornado.options import options
from tornado.test.util import unittest
from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application
from tornado.websocket import websocket_connect

from bin.server import TermSocketHandler

TOKEN_ALGORITHM_ENCODING = 'HS256'

TOKEN_KEY = 'secret'

TOKEN_TTL = 15

USER_ID = 1

ENCODED_TOKEN = jwt.encode({'user_id': USER_ID, 'ip': '127.0.0.1'}, TOKEN_KEY,
                           algorithm=TOKEN_ALGORITHM_ENCODING).decode('utf8')


class LockedRPCServer(TermSocketHandler):
    def __init__(self, application, request, **kwargs):
        TermSocketHandler.__init__(self, application, request, **kwargs)

    def initialize(self, close_future, compression_options=None):
        self.close_future = close_future
        self.compression_options = compression_options

    def get_compression_options(self):
        return self.compression_options

    def on_close(self):
        self.close_future.set_result((self.close_code, self.close_reason))


class UnlockedRPCServer(LockedRPCServer):
    def __init__(self, application, request, **kwargs):
        LockedRPCServer.__init__(self, application, request, **kwargs)
        self.global_lock = False


class WebSocketBaseTestCase(AsyncHTTPTestCase):
    @gen.coroutine
    def ws_connect(self, path, compression_options=None):
        ws = yield websocket_connect('ws://127.0.0.1:{}{}'.format(
            self.get_http_port(), path
        ), compression_options=compression_options)
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, ws):
        """Close a websocket connection and wait for the server side.

        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        ws.close()
        yield self.close_future
    

class RPCServerTest(WebSocketBaseTestCase):
    def get_app(self):
        self.close_future = Future()
        redis_conn = redis.StrictRedis(host='localhost', port=6379, db=0)
        key = 'user:{}:token'.format(USER_ID)
        redis_conn.setex(key, 60 * TOKEN_TTL, ENCODED_TOKEN)
        options.token_algorithm = TOKEN_ALGORITHM_ENCODING
        options.token_key = TOKEN_KEY
        return Application([
            ('/locked_rpc/token/' + TOKEN_PATTERN, LockedRPCServer,
             dict(close_future=self.close_future)),
            ('/unlocked_rpc/token/' + TOKEN_PATTERN, UnlockedRPCServer,
             dict(close_future=self.close_future)),
        ])

    def prepare_payload(self, procedure_name, parameters_list, marker):
        data = {
            'function_name': procedure_name,
            'parameters_list': parameters_list,
            'marker': marker
        }
        return json_encode(data)

    @gen_test
    def test_starting(self):
        ws = yield self.ws_connect('/locked_rpc/token/' + ENCODED_TOKEN)
        payload = self.prepare_payload('start', ['some_image_name'], 1)
        ws.write_message(payload)
        response = yield ws.read_message()
        self.assertEqual(json_decode(response), {
            'result': 1,
            'marker': 1,
            'eod': 1,
        })
        yield self.close(ws)

if __name__ == '__main__':
    unittest.main()
