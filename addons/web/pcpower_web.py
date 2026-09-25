#!/usr/bin/env python3
"""Optional browser interface for the local pcpowerd socket protocol."""

import base64
import hmac
import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit


LOG = logging.getLogger("pcpower_web")
SOCKET_PATH = "/run/pcpower/control.sock"
PASSWORD_PATH = "/etc/pcpower/web-password"
ASSETS = Path(__file__).with_name("web")
LISTEN = "0.0.0.0"
PORT = 8766
SOCKET_TIMEOUT = 90


def daemon_request(payload):
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SOCKET_TIMEOUT)
        connection.connect(SOCKET_PATH)
        connection.sendall(data)
        with connection.makefile("rb") as stream:
            response = stream.readline(65537)
    if not response or len(response) > 65536 or not response.endswith(b"\n"):
        raise ValueError("Invalid response from pcpowerd")
    result = json.loads(response)
    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
        raise ValueError("Invalid response from pcpowerd")
    return result


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, password):
        credential = base64.b64encode(f"pcpower:{password}".encode()).decode()
        self.expected_authorization = f"Basic {credential}"
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    @property
    def app_server(self) -> Server:
        return cast(Server, self.server)

    def respond(self, code, body, content_type="application/json; charset=utf-8",
                extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def respond_json(self, code, value, extra_headers=None):
        self.respond(code, json.dumps(value, separators=(",", ":")).encode() + b"\n",
                     extra_headers=extra_headers)

    def authenticated(self):
        if hmac.compare_digest(
            self.headers.get("Authorization", ""),
            self.app_server.expected_authorization,
        ):
            return True
        self.respond_json(401, {"error": "Authentication required"},
                          {"WWW-Authenticate": 'Basic realm="PC power"'})
        return False

    def daemon_result(self, payload):
        try:
            response = daemon_request(payload)
        except (OSError, ValueError) as error:
            LOG.warning("pcpowerd request failed: %s", error)
            self.respond_json(502, {"error": "Cannot reach pcpowerd"})
            return None
        if not response["ok"]:
            message = response.get("error", {}).get("message", "Daemon action failed")
            self.respond_json(422, {"error": str(message)})
            return None
        return response.get("result")

    def machine_route(self, path):
        parts = path.split("/")
        if len(parts) != 5 or parts[:3] != ["", "api", "machines"]:
            return None
        machine = unquote(parts[3])
        if not machine or "/" in machine or "\x00" in machine:
            return None
        return machine, parts[4]

    def snapshot(self):
        listing = self.daemon_result({"action": "list"})
        if listing is None:
            return
        if not isinstance(listing, dict) or not isinstance(listing.get("machines"), list):
            self.respond_json(502, {"error": "Invalid machine list"})
            return

        names = listing["machines"]

        def read_status(name):
            try:
                response = daemon_request({"action": "status", "machine": name})
                if response["ok"]:
                    return {"name": name, "status": response.get("result")}
                return {"name": name, "error": str(response.get("error", {}).get("message", "Status failed"))}
            except (OSError, ValueError) as error:
                return {"name": name, "error": str(error)}

        with ThreadPoolExecutor(max_workers=8) as workers:
            machines = list(workers.map(read_status, names))
        self.respond_json(200, {"machines": machines})

    def do_GET(self):
        if not self.authenticated():
            return
        path = urlsplit(self.path)
        if path.query or path.fragment:
            self.respond_json(404, {"error": "Unknown endpoint"})
            return
        if path.path in ("/", "/app.js", "/style.css"):
            filename, content_type = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }[path.path]
            self.respond(200, (ASSETS / filename).read_bytes(), content_type)
        elif path.path == "/api/snapshot":
            self.snapshot()
        elif path.path == "/api/health":
            result = self.daemon_result({"action": "health"})
            if result is not None:
                self.respond_json(200, result)
        else:
            route = self.machine_route(path.path)
            if route and route[1] in ("inputs", "raw"):
                result = self.daemon_result({"action": route[1], "machine": route[0]})
                if result is not None:
                    self.respond_json(200, result)
            else:
                self.respond_json(404, {"error": "Unknown endpoint"})

    def do_POST(self):
        if not self.authenticated():
            return
        # Custom header makes browser cross-site form submissions insufficient.
        origin = self.headers.get("Origin")
        if (self.headers.get("X-PCPower-Web") != "1"
                or (origin and origin != f"http://{self.headers.get('Host', '')}")):
            self.respond_json(403, {"error": "Request origin rejected"})
            return
        path = urlsplit(self.path)
        if path.query or path.fragment:
            self.respond_json(404, {"error": "Unknown endpoint"})
            return
        if path.path == "/api/reload":
            payload = {"action": "reload"}
        else:
            route = self.machine_route(path.path)
            if route is None:
                self.respond_json(404, {"error": "Unknown endpoint"})
                return
            machine, action = route
            if action in ("on", "off", "reset"):
                payload = {"action": action, "machine": machine}
            elif action in ("press-power", "press-reset"):
                payload = {"action": "press", "machine": machine,
                           "button": action.split("-", 1)[1]}
            else:
                self.respond_json(404, {"error": "Unknown endpoint"})
                return
        result = self.daemon_result(payload)
        if result is not None:
            self.respond_json(200, result)


def main():
    password = Path(PASSWORD_PATH).read_text(encoding="utf-8").strip()
    if not password or "\n" in password or "\r" in password:
        raise SystemExit("web-password must contain exactly one nonempty password")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    server = Server((LISTEN, PORT), password)
    LOG.info("Web UI listening on %s:%d", LISTEN, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
