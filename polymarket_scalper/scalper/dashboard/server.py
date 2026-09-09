"""Servidor local del panel: sirve la página y /api/all con los datos frescos. Solo librería estándar."""
from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import Config
from .data import build_payload

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


class _Cache:
    def __init__(self, cfg: Config, ttl: float):
        self.cfg, self.ttl = cfg, ttl
        self._lock = threading.Lock()
        self._at = 0.0
        self._payload: bytes = b"{}"

    def get(self) -> bytes:
        with self._lock:
            if time.time() - self._at > self.ttl:
                try:
                    self._payload = json.dumps(build_payload(self.cfg), default=str).encode("utf-8")
                except Exception as e:  # noqa: BLE001
                    log.exception("no se pudo armar el payload")
                    self._payload = json.dumps({"error": str(e)}).encode("utf-8")
                self._at = time.time()
            return self._payload


def make_handler(cache: _Cache):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # silencioso
            pass

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                body = (STATIC / "index.html").read_bytes()
                self._send(200, "text/html; charset=utf-8", body)
            elif path == "/api/all":
                self._send(200, "application/json; charset=utf-8", cache.get())
            elif path == "/health":
                self._send(200, "application/json", b'{"ok":true}')
            else:
                self._send(404, "text/plain", b"not found")

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(cfg: Config, host: str = "127.0.0.1", port: int = 8787, refresh_seconds: float = 10) -> None:
    cache = _Cache(cfg, refresh_seconds)
    srv = ThreadingHTTPServer((host, port), make_handler(cache))
    log.info("panel en http://%s:%d  (datos: %s, refresco %.0fs)", host, port, cfg.data_dir, refresh_seconds)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
