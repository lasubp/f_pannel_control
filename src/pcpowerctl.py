#!/usr/bin/env python3

import argparse
import json
import socket
import sys

DEFAULT_SOCKET = "/run/pcpower/control.sock"


def request(socket_path, payload):
    data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path)
        sock.sendall(data)
        with sock.makefile("rb") as file:
            response = file.readline()

    if not response:
        raise RuntimeError("daemon closed connection")

    return json.loads(response.decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(prog="pcpowerctl")
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    parser.add_argument("--json", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("health")

    # Reload the daemon's config file from disk without
    # restarting the service or losing in-flight state.
    # Equivalent to `kill -HUP <pcpowerd pid>`.
    sub.add_parser("reload")

    for command in ("status", "inputs", "raw", "on", "off", "reset"):
        p = sub.add_parser(command)
        p.add_argument("machine")

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

    press_parser = sub.add_parser("press")
    press_parser.add_argument("button", choices=("power", "reset"))
    press_parser.add_argument("machine")
    press_parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="button duration in milliseconds",
    )

    args = parser.parse_args()
    payload = {"action": args.command}

    if hasattr(args, "machine"):
        payload["machine"] = args.machine

    if args.command == "press":
        payload["button"] = args.button
        if args.duration is not None:
            if args.duration <= 0:
                parser.error("--duration must be greater than 0")
            payload["duration_ms"] = args.duration

    try:
        response = request(args.socket, payload)
    except Exception as error:
        print(f"pcpowerctl: {error}", file=sys.stderr)
        return 2

    if not response.get("ok"):
        message = response.get("error", {}).get("message", "unknown daemon error")
        print(message, file=sys.stderr)
        return 1

    result = response.get("result")

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "list":
        for machine in result["machines"]:
            print(machine)

    elif args.command == "health":
        print(json.dumps(result, indent=2))

    elif args.command == "reload":
        machines = ", ".join(result.get("machines", []))
        print(f"Reloaded config. Machines: {machines}")

    elif args.command == "raw":
        print(f'{result["name"]}: {result["hex"]} ({result["binary"]})')
        print(" ".join(
            f"{pin}={1 if value else 0}"
            for pin, value in result["pins"].items()
        ))

    elif args.command == "inputs":
        power = "ON" if result["power_led"] else "OFF"
        hdd_value = result.get("hdd_led")
        hdd = "N/A" if hdd_value is None else ("ON" if hdd_value else "OFF")
        print(f'{result["name"]}: PWR_LED={power} HDD_LED={hdd}')

    elif args.command == "press":
        print(
            f'{result["name"]}: {result["button"]} pressed '
            f'for {result["duration_ms"]} ms'
        )

    else:
        text = f'{result["name"]}: {result["power"]}'
        if result.get("hdd") is not None:
            text += f' hdd={result["hdd"]}'
        print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())