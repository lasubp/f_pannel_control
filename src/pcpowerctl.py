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

        response = (
            file.readline()
        )

        if not response:
            raise RuntimeError(
                "daemon closed connection"
            )

        return json.loads(
            response.decode(
                "utf-8"
            )
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

    sub.add_parser(
        "list"
    )

    sub.add_parser(
        "health"
    )

    for command in (
        "status",
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

    if args.json:

        print(
            json.dumps(
                response,
                indent=2
            )
        )

    elif not response.get(
        "ok"
    ):

        print(
            response[
                "error"
            ][
                "message"
            ],
            file=sys.stderr
        )

        return 1

    else:

        result = response[
            "result"
        ]

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

        else:

            line = (
                f'{result["name"]}: '
                f'{result["power"]}'
            )

            if (
                result.get("hdd")
                is not None
            ):
                line += (
                    f' hdd={result["hdd"]}'
                )

            print(line)

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )