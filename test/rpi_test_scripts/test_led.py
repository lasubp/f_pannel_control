#!/usr/bin/env python3
import time
from smbus2 import SMBus

bus = SMBus(1)
bus.write_byte(0x20, 0xFF)

while True:
    value = bus.read_byte(0x20)
    print(f"\rRaw: 0x{value:02X}  P2: {(value >> 2) & 1}", end="")
    time.sleep(0.1)