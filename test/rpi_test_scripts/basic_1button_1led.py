#!/usr/bin/env python3
import select
import sys
import time
from smbus2 import SMBus

ADDR = 0x20
bus = SMBus(1)
pressed_until = 0

print("Enter = press button | q + Enter = quit")

try:
    while True:
        if select.select([sys.stdin], [], [], 0)[0]:
            if sys.stdin.readline().strip().lower() == "q":
                break
            pressed_until = time.monotonic() + 0.5

        pressed = time.monotonic() < pressed_until
        bus.write_byte(ADDR, 0xFE if pressed else 0xFF)

        value = bus.read_byte(ADDR)
        led_on = not bool(value & 0x04)

        print(
            f"\rButton: {'PRESSED ' if pressed else 'released'} | "
            f"LED: {'ON ' if led_on else 'OFF'}",
            end="",
            flush=True,
        )
        time.sleep(0.05)

finally:
    bus.write_byte(ADDR, 0xFF)
    print("\nStopped")