#!/usr/bin/env python3

import argparse
import json
import logging
import os
import signal
import socketserver
import stat
import sys
import threading
from typing import cast

from pcpower_core import (
    Controller,
    PCPowerError,
    load_config
)


LOG = logging.getLogger("pcpowerd")


class ThreadingUnixServer(
    socketserver.ThreadingMixIn,
    socketserver.UnixStreamServer
):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        socket_path,
        handler_class,
        controller,
        config_path
    ):
        self.controller = controller
        self.config_path = config_path

        super().__init__(
            socket_path,
            handler_class
        )


class RequestHandler(
    socketserver.StreamRequestHandler
):

    MAX_REQUEST = 64 * 1024
    
    @property
    def app_server(self) -> ThreadingUnixServer:
        return cast(ThreadingUnixServer, self.server)

    def send_response(
        self,
        ok,
        result=None,
        error=None
    ):
        response = {
            "ok": ok
        }

        if ok:
            response["result"] = result

        else:
            response["error"] = {
                "message": str(error)
            }

        data = (
            json.dumps(
                response,
                separators=(",", ":")
            )
            + "\n"
        )

        self.wfile.write(
            data.encode("utf-8")
        )

        self.wfile.flush()

    def _dispatch(self, request):

        action = request.get(
            "action"
        )

        controller = self.app_server.controller

        # --------------------------------
        # Generic operations
        # --------------------------------

        if action == "list":

            return {
                "machines":
                controller.list_machines()
            }

        if action == "health":

            return controller.health()

        if action == "reload":

            controller.reload(
                self.app_server.config_path
            )

            return {
                "reloaded": True,
                "machines":
                    controller.list_machines()
            }

        # --------------------------------
        # Machine operations
        # --------------------------------

        machine_name = request.get(
            "machine"
        )

        if not machine_name:
            raise PCPowerError(
                "machine is required"
            )

        machine = controller.get(
            machine_name
        )

        if action == "status":
            return machine.status()
        
        if action == "inputs":
            return machine.inputs()
        
        if action == "raw":
            return machine.raw()
        
        if action == "press":
            button = request.get(
                "button"
            )

            if not button:
                raise PCPowerError(
                    "button is required"
                )

            duration_ms = request.get(
                "duration_ms"
            )

            return machine.debug_press(
                button,
                duration_ms
            )

        if action == "on":
            return machine.power_on()

        if action == "off":
            return machine.power_off()

        if action == "reset":
            return machine.reset()

        raise PCPowerError(
            f"Unknown action: {action}"
        )

    def dispatch(self, request):
        if request.get("action") == "reload":
            return self._dispatch(request)

        with self.app_server.controller.operation():
            return self._dispatch(request)

    def handle(self):

        while True:

            raw = self.rfile.readline(
                self.MAX_REQUEST + 1
            )

            if not raw:
                return

            if len(raw) > self.MAX_REQUEST:

                self.send_response(
                    False,
                    error="request too large"
                )

                return

            try:

                request = json.loads(
                    raw.decode("utf-8")
                )

                if not isinstance(
                    request,
                    dict
                ):
                    raise PCPowerError(
                        "request must be object"
                    )

                result = self.dispatch(
                    request
                )

                self.send_response(
                    True,
                    result=result
                )

            except Exception as error:

                LOG.exception(
                    "Request failed"
                )

                # The client may already be gone (crashed,
                # timed out, closed the socket); don't let a
                # failed error-report kill the handler thread.
                try:
                    self.send_response(
                        False,
                        error=error
                    )

                except (
                    BrokenPipeError,
                    ConnectionResetError
                ):
                    return


def prepare_socket(path):

    parent = os.path.dirname(
        path
    )

    os.makedirs(
        parent,
        exist_ok=True
    )

    if os.path.exists(path):

        mode = os.stat(
            path
        ).st_mode

        if not stat.S_ISSOCK(
            mode
        ):
            raise RuntimeError(
                f"{path} exists and "
                "is not a socket"
            )

        os.unlink(
            path
        )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config",
        default="/etc/pcpower/config.yaml"
    )

    parser.add_argument(
        "--socket",
        default="/run/pcpower/control.sock"
    )

    parser.add_argument(
        "--check",
        action="store_true"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        )
    )

    config = load_config(
        args.config
    )

    controller = Controller(
        config
    )

    if args.check:

        try:
            print(
                json.dumps(
                    controller.health(),
                    indent=2
                )
            )

            return 0

        finally:
            controller.close()

    prepare_socket(
        args.socket
    )

    server = ThreadingUnixServer(
        args.socket,
        RequestHandler,
        controller,
        args.config
    )

    # Allow owner + pcpower group.
    os.chmod(
        args.socket,
        0o660
    )

    stopping = threading.Event()

    def stop(
        signum,
        frame
    ):
        del frame

        if stopping.is_set():
            return

        stopping.set()

        LOG.info(
            "Stopping on signal %d",
            signum
        )

        threading.Thread(
            target=server.shutdown,
            daemon=True
        ).start()

    def do_reload():

        try:
            controller.reload(
                args.config
            )

            LOG.info(
                "Reload complete. Machines: %s",
                ", ".join(
                    controller.list_machines()
                )
            )

        except Exception as error:

            LOG.error(
                "Reload failed, keeping previous "
                "configuration: %s",
                error
            )

    def reload_signal(
        signum,
        frame
    ):
        del frame

        LOG.info(
            "Reload requested (signal %d)",
            signum
        )

        # Do the actual I2C/config work off the signal
        # handler, same as shutdown does.
        threading.Thread(
            target=do_reload,
            daemon=True
        ).start()

    signal.signal(
        signal.SIGTERM,
        stop
    )

    signal.signal(
        signal.SIGINT,
        stop
    )

    signal.signal(
        signal.SIGHUP,
        reload_signal
    )

    LOG.info(
        "Machines: %s",
        ", ".join(
            controller.list_machines()
        )
    )

    LOG.info(
        "Socket: %s",
        args.socket
    )

    try:

        server.serve_forever(
            poll_interval=0.5
        )

    finally:

        server.server_close()

        controller.close()

        try:
            os.unlink(
                args.socket
            )
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )