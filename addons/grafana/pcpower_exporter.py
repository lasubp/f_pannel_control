#!/usr/bin/env python3
"""Optional Prometheus exporter for the pcpowerd Unix socket."""

import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LOG = logging.getLogger("pcpower_exporter")
SOCKET_PATH = "/run/pcpower/control.sock"
LISTEN = "0.0.0.0"
PORT = 9108
SOCKET_TIMEOUT = 5


def daemon_request(action, machine=None):
    payload = {"action": action}
    if machine is not None:
        payload["machine"] = machine
    request = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SOCKET_TIMEOUT)
        connection.connect(SOCKET_PATH)
        connection.sendall(request)
        with connection.makefile("rb") as stream:
            response = stream.readline(65537)
    if not response or len(response) > 65536 or not response.endswith(b"\n"):
        raise ValueError("Invalid response from pcpowerd")
    data = json.loads(response)
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        raise ValueError("Invalid response from pcpowerd")
    if not data["ok"]:
        raise ValueError(str(data.get("error", {}).get("message", "Daemon error")))
    return data.get("result")


def label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metric(lines, name, help_text, samples):
    lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge"))
    for labels, value in samples:
        suffix = "{" + ",".join(f'{key}="{label(item)}"' for key, item in labels.items()) + "}" if labels else ""
        lines.append(f"{name}{suffix} {value}")


def collect():
    lines = []
    try:
        listing = daemon_request("list")
        names = listing["machines"]
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError("Invalid machine list")
    except (OSError, ValueError, KeyError, TypeError) as error:
        LOG.warning("Cannot list machines: %s", error)
        metric(lines, "pcpower_daemon_up", "Can the exporter read the daemon machine list.", [({}, 0)])
        return "\n".join(lines) + "\n"

    metric(lines, "pcpower_daemon_up", "Can the exporter read the daemon machine list.", [({}, 1)])
    metric(lines, "pcpower_machines_configured", "Machines in the current daemon configuration.", [({}, len(names))])

    def read_status(name):
        try:
            result = daemon_request("status", name)
            if not isinstance(result, dict) or result.get("power") not in ("on", "off"):
                raise ValueError("Invalid machine status")
            return result
        except (OSError, ValueError) as error:
            LOG.warning("Cannot read %s: %s", name, error)
            return None

    with ThreadPoolExecutor(max_workers=8) as workers:
        statuses = dict(zip(names, workers.map(read_status, names)))

    metric(lines, "pcpower_machine_status_up", "Can the daemon read this machine status.",
           [({"machine": name}, int(statuses[name] is not None)) for name in names])
    metric(lines, "pcpower_machine_power_state", "Power LED state: 1 on, 0 off; absent if unreadable.",
           [({"machine": name}, int(statuses[name]["power"] == "on"))
            for name in names if statuses[name] is not None])
    metric(lines, "pcpower_machine_hdd_led_configured", "Whether an HDD LED is configured for this machine.",
           [({"machine": name}, int(statuses[name].get("hdd") is not None))
            for name in names if statuses[name] is not None])
    metric(lines, "pcpower_machine_hdd_led_active", "HDD LED activity: 1 active, 0 idle; absent if unconfigured or unreadable.",
           [({"machine": name}, int(statuses[name]["hdd"] == "active"))
            for name in names if statuses[name] is not None and statuses[name].get("hdd") is not None])

    try:
        health = daemon_request("health")
        devices = health["devices"]
        if not isinstance(devices, dict):
            raise ValueError("Invalid device health")
        metric(lines, "pcpower_i2c_health_up", "Can the daemon report I2C device health.", [({}, 1)])
        metric(lines, "pcpower_expander_up", "Whether this I2C expander responded to the daemon.",
               [({"device": name}, int(bool(info["ok"]))) for name, info in devices.items()])
    except (OSError, ValueError, KeyError, TypeError) as error:
        LOG.warning("Cannot read I2C health: %s", error)
        metric(lines, "pcpower_i2c_health_up", "Can the daemon report I2C device health.", [({}, 0)])

    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        body = collect().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    server = ThreadingHTTPServer((LISTEN, PORT), Handler)
    server.daemon_threads = True
    LOG.info("Metrics listening on %s:%d", LISTEN, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
