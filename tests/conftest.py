"""A real HTTP server for the few tests that must exercise the socket itself."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

_BODIES: dict[str, dict[str, object]] = {
    "/health": {"status": "ok", "version": "0.5.1"},
    "/v1/search": {
        "sources": [],
        "latency_ms": 1,
        "sufficient_evidence": True,
        "min_evidence_score": 0.0,
    },
}


class _Handler(BaseHTTPRequestHandler):
    # Keep-alive is the whole point: a pooled connection is what carries a dead
    # event loop from one run to the next. HTTP/1.0 would close after every
    # response and quietly hide the bug this server exists to expose.
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._respond()

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        self.rfile.read(length)
        self._respond()

    def _respond(self) -> None:
        body = json.dumps(_BODIES.get(self.path, {})).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output clean."""


@pytest.fixture
def reed_socket() -> Iterator[str]:
    """A stand-in reed on a real port, so the HTTP transport is genuinely used."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
