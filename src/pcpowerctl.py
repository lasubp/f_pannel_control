#!/usr/bin/env python3

import argparse
import json
import socket
import sys


DEFAULT_SOCKET = (
    "/run/pcpower/control.sock"
)


def request(
    socket_path,
    payload
):

    data = (
        json.dumps(
            payload,
            separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")

    sock = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM
    )

    try:

        sock.connect(
            socket_path
        )

        sock.sendall(
            data
        )

        file = sock.makefile(
            "rb"
        )

        response = file.readline()

        if not response:
            raise RuntimeError(
                "daemon closed connection"
            )

        return json.loads(
            response.decode("utf-8")
        )

    finally:
        sock.close()


def main():

    parser = argparse.ArgumentParser(
        prog="pcpowerctl"
    )

    parser.add_argument(
        "--socket",
        default=DEFAULT_SOCKET
    )

    parser.add_argument(
        "--json",
        action="store_true"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True
    )

    sub.add_parser("list")
    sub.add_parser("health")

    for command in (
        "status",
        "inputs",
        "raw",
        "on",
        "off",
        "reset"
    ):

        p = sub.add_parser(
            command
        )

        p.add_argument(
            "machine"
        )

    # --------------------------------------------------------
    # Low-level button diagnostic
    #
    # pcpowerctl press power pc1
    # pcpowerctl press reset pc1
    #
    # optionally:
    #
    # pcpowerctl press power pc1 --duration 1000
    # --------------------------------------------------------

    press_parser = sub.add_parser(
        "press"
    )

    press_parser.add_argument(
        "button",
        choices=[
            "power",
            "reset"
        ]
    )

    press_parser.add_argument(
        "machine"
    )

    press_parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="button duration in milliseconds"
    )

    args = parser.parse_args()

    payload = {
        "action":
            args.command
    }

    if hasattr(
        args,
        "machine"
    ):
        payload["machine"] = (
            args.machine
        )

    if args.command == "press":

        payload["button"] = (
            args.button
        )

        if args.duration is not None:

            payload["duration_ms"] = (
                args.duration
            )

    try:

        response = request(
            args.socket,
            payload
        )

    except Exception as error:

        print(
            f"pcpowerctl: {error}",
            file=sys.stderr
        )

        return 2

    if not response.get("ok"):

        print(
            response[
                "error"
            ][
                "message"
            ],
            file=sys.stderr
        )

        return 1

    result = response["result"]

    if args.json:

        print(
            json.dumps(
                result,
                indent=2
            )
        )

        return 0

    # --------------------------------------------------------
    # Human-readable output
    # --------------------------------------------------------

    if args.command == "list":

        for machine in (
            result["machines"]
        ):
            print(machine)

    elif args.command == "health":

        print(
            json.dumps(
                result,
                indent=2
            )
        )

    elif args.command == "raw":

        print(
            f'{result["name"]}: '
            f'{result["hex"]} '
            f'({result["binary"]})'
        )

        pins = result["pins"]

        print(
            " ".join(
                f"{pin}="
                f"{1 if value else 0}"
                for pin, value
                in pins.items()
            )
        )

    elif args.command == "inputs":

        print(
            f'{result["name"]}: '
            f'PWR_LED='
            f'{"ON" if result["power_led"] else "OFF"} '
            f'HDD_LED='
            f'{"ON" if result["hdd_led"] else "OFF"}'
        )

    elif args.command == "press":

        print(
            f'{result["name"]}: '
            f'{result["button"]} pressed '
            f'for {result["duration_ms"]} ms'
        )

    else:

        print(
            f'{result["name"]}: '
            f'{result["power"]}'
            + (
                f' hdd={result["hdd"]}'
                if result.get("hdd") is not None
                else ""
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )