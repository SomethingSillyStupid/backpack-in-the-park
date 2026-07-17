import asyncio
import gc
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeReader:
    def __init__(self, body, declared_length=13):
        self.data = b"".join(
            (
                b"POST /post HTTP/1.1\r\n",
                b"Content-Type: application/x-www-form-urlencoded\r\n",
                ("Content-Length: %d\r\n" % declared_length).encode("ascii"),
                b"\r\n",
                body,
            )
        )

    async def readline(self):
        newline = self.data.find(b"\n")
        if newline == -1:
            line, self.data = self.data, b""
            return line
        line, self.data = self.data[: newline + 1], self.data[newline + 1 :]
        return line

    async def read(self, size):
        chunk = self.data[:size]
        self.data = self.data[size:]
        return chunk


class BoundedStreamReader:
    def __init__(self, data):
        self.data = data
        self.read_sizes = []

    async def readline(self):
        raise AssertionError("unbounded readline() must not be used")

    async def read(self, size):
        self.read_sizes.append(size)
        chunk = self.data[:size]
        self.data = self.data[size:]
        return chunk


class FakeWriter:
    def __init__(self):
        self.data = bytearray()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.data.extend(data)

    async def drain(self):
        return None

    def close(self):
        return None

    async def wait_closed(self):
        return None


class PhewTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.import_loop)
        if not hasattr(gc, "threshold"):
            setattr(gc, "threshold", lambda value: None)
        machine = types.ModuleType("machine")
        with patch.dict(sys.modules, {"uasyncio": asyncio, "machine": machine}):
            cls.server = importlib.import_module("phew.server")
        cls.server.time.ticks_ms = lambda: 0
        cls.server.logging.info = lambda *items: None
        cls.server.logging.error = lambda *items: None

    @classmethod
    def tearDownClass(cls):
        cls.import_loop.close()
        asyncio.set_event_loop(None)

    def run_request(self, body, declared_length=13):
        reader = FakeReader(body, declared_length)
        writer = FakeWriter()
        asyncio.run(self.server._handle_request(reader, writer))
        return bytes(writer.data)

    def run_stream(self, data):
        reader = BoundedStreamReader(data)
        writer = FakeWriter()
        asyncio.run(self.server._handle_request(reader, writer))
        return bytes(writer.data), reader.read_sizes

    def test_truncated_urlencoded_body_returns_400(self):
        response = self.run_request(b"message=hel")
        self.assertTrue(response.startswith(b"HTTP/1.1 400 Bad Request\r\n"))

    def test_malformed_urlencoded_body_returns_400(self):
        body = b"message=%ZZx"
        response = self.run_request(body, len(body))
        self.assertTrue(response.startswith(b"HTTP/1.1 400 Bad Request\r\n"))

    def test_oversized_request_line_is_rejected_without_unbounded_readline(self):
        request = b"GET /" + (b"x" * 600) + b" HTTP/1.1\r\n\r\n"
        response, read_sizes = self.run_stream(request)
        self.assertTrue(response.startswith(b"HTTP/1.1 400 Bad Request\r\n"))
        self.assertEqual(set(read_sizes), {1})

    def test_oversized_header_line_is_rejected_without_unbounded_readline(self):
        request = b"GET / HTTP/1.1\r\nX-Fill: " + (b"x" * 1100) + b"\r\n\r\n"
        response, read_sizes = self.run_stream(request)
        self.assertTrue(response.startswith(b"HTTP/1.1 400 Bad Request\r\n"))
        self.assertEqual(set(read_sizes), {1})

    def test_aggregate_headers_are_bounded(self):
        headers = b"".join(b"X-%02d: %s\r\n" % (index, b"x" * 90) for index in range(50))
        response, read_sizes = self.run_stream(b"GET / HTTP/1.1\r\n" + headers + b"\r\n")
        self.assertTrue(response.startswith(b"HTTP/1.1 400 Bad Request\r\n"))
        self.assertEqual(set(read_sizes), {1})


if __name__ == "__main__":
    unittest.main()
