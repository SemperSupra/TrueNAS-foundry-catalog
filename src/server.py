#!/usr/bin/env python3
"""Standalone TLS-only browser/API adapter for pinned Foundry read-only core.

Product-specific presentation only; never a second source inventory or actuator.
"""
from __future__ import annotations

import argparse
import json
import ssl
import stat
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "vendor"))

import foundry_catalog_federation as federation
import foundry_catalog_read_http as read_gateway

CONTENT_TYPES = {"/": "text/html; charset=utf-8", "/app.js": "text/javascript; charset=utf-8", "/app.css": "text/css; charset=utf-8"}
STATIC_FILES = {"/": "index.html", "/app.js": "app.js", "/app.css": "app.css"}
MAX_ASSET_BYTES = 200_000


class ProductConfigurationError(ValueError):
    pass


def check_file(path: Path, private: bool = False) -> None:
    if path.is_symlink():
        raise ProductConfigurationError("configuration file must not be a symlink")
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ProductConfigurationError("configuration must be a regular file")
    if private and mode & 0o077:
        raise ProductConfigurationError("private key/secret must be owner-only")


class ProductHandler(read_gateway.ReadHandler):
    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
        except ValueError:
            self.respond(400, {"error": "invalid request"})
            return
        if parsed.path == "/healthz" and not parsed.query and not parsed.fragment:
            self.respond(200, {"status": "READY", "mode": "READ_ONLY"})
            return
        if parsed.path in STATIC_FILES and not parsed.query and not parsed.fragment:
            file = HERE / "assets" / STATIC_FILES[parsed.path]
            data = file.read_bytes()
            if len(data) > MAX_ASSET_BYTES:
                self.respond(500, {"error": "asset exceeds resource budget"})
                return
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPES[parsed.path])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


class ProductServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, bind: str, port: int, rows: list[dict], bearer: str, tls: ssl.SSLContext):
        if bind not in {"0.0.0.0", "127.0.0.1"}:
            raise ProductConfigurationError("IPv4 bind must be explicit and supported")
        if not 0 <= port <= 65535:
            raise ProductConfigurationError("invalid port")
        if not isinstance(bearer, str) or len(bearer) < 32:
            raise ProductConfigurationError("strong authentication token required")
        self.rows = tuple(dict(row) for row in rows)
        self.bearer = bearer
        super().__init__((bind, port), ProductHandler)
        self.socket = tls.wrap_socket(self.socket, server_side=True)


def configure_tls(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    check_file(cert_file)
    check_file(key_file, private=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, action="append", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--tls-cert-file", type=Path, required=True)
    parser.add_argument("--tls-key-file", type=Path, required=True)
    parser.add_argument("--bind", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args(argv)
    try:
        rows = federation.load_catalogs(args.index)
        bearer = read_gateway.load_bearer(args.token_file)
        tls = configure_tls(args.tls_cert_file, args.tls_key_file)
        with ProductServer(args.bind, args.port, rows, bearer, tls) as service:
            print(json.dumps({"status": "READY", "mode": "TLS_READ_ONLY", "port": service.server_port}), flush=True)
            service.serve_forever()
        return 0
    except (OSError, ValueError, ssl.SSLError, federation.CatalogIdentityError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
