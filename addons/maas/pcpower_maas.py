#!/usr/bin/env python3
"""Optional MAAS Webhook power adapter for the pcpowerd Unix socket."""

import argparse
import hmac
import json
import logging
import socket
from typing import cast
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


LOG = logging.getLogger("pcpower_maas")


def daemon_request(socket_path, action, machine, timeout):
    request = json.dumps(
        {"action": action, "machine": machine}, separators=(",", ":")
    ).encode("utf-8") + b"\n"

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(socket_path)
        connection.sendall(request)
        with connection.makefile("rb") as stream:
            response = stream.readline(65537)

    if not response or len(response) > 65536 or not response.endswith(b"\n"):
        raise ValueError("Invalid response from pcpowerd")

    data = json.loads(response)
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        raise ValueError("Invalid response from pcpowerd")
    return data


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, socket_path, token, timeout):
        self.socket_path = socket_path
        self.token = token
        self.daemon_timeout = timeout
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    @property
    def app_server(self) -> Server:
        return cast(Server, self.server)

    def send_json(self, status, value):
        body = json.dumps(value, separators=(",", ":")).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def handle_action(self):
        expected = "Bearer " + self.app_server.token
        if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            self.send_json(401, {"error": "Unauthorized"})
            return

        path = urlsplit(self.path)
        parts = path.path.split("/")
        if (path.query or path.fragment or len(parts) != 5
                or parts[:3] != ["", "v1", "machines"]):
            self.send_json(404, {"error": "Unknown endpoint"})
            return

        machine = unquote(parts[3])
        operation = parts[4]
        if not machine or "/" in machine or "\x00" in machine:
            self.send_json(404, {"error": "Unknown endpoint"})
            return

        action = {"on": "on", "off": "off", "query": "status"}.get(operation)
        if action is None or (self.command, operation) not in (
            ("POST", "on"), ("POST", "off"), ("GET", "query")
        ):
            self.send_json(404, {"error": "Unknown endpoint"})
            return

        try:
            reply = daemon_request(
                self.app_server.socket_path, action, machine, self.app_server.daemon_timeout
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            LOG.warning("Daemon request failed: %s", error)
            self.send_json(502, {"error": "pcpowerd unavailable or invalid response"})
            return

        if not reply["ok"]:
            message = reply.get("error", {}).get("message", "Daemon action failed")
            LOG.warning("%s on %s failed: %s", action, machine, message)
            self.send_json(502, {"error": str(message)})
            return

        result = reply.get("result")
        if not isinstance(result, dict) or result.get("power") not in ("on", "off"):
            LOG.warning("Invalid status from pcpowerd for %s", machine)
            self.send_json(502, {"error": "Invalid power status from pcpowerd"})
            return

        self.send_json(200, {"power_state": result["power"]})

    def do_GET(self):
        self.handle_action()

    def do_POST(self):
        self.handle_action()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1", help="IP address to bind")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--socket", default="/run/pcpower/control.sock")
    parser.add_argument("--token-file", required=True, help="File containing MAAS bearer token")
    parser.add_argument("--timeout", type=float, default=90.0,
                        help="Seconds to wait for a daemon response")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or args.timeout <= 0:
        parser.error("port must be 1..65535 and timeout must be positive")

    with open(args.token_file, encoding="utf-8") as stream:
        token = stream.read().strip()
    if not token or "\r" in token or "\n" in token:
        parser.error("token file must contain exactly one nonempty token")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    server = Server((args.listen, args.port), args.socket, token, args.timeout)
    LOG.info("Listening on %s:%s", args.listen, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
