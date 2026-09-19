#!/usr/bin/env python3

import json
import threading
import time

from smbus2 import SMBus


class PCPowerError(Exception):
    pass


def parse_int(value):
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        return int(value, 0)

    raise PCPowerError(
        f"Invalid integer value: {value!r}"
    )


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise PCPowerError(
            "Configuration root must be an object"
        )

    return config


# ============================================================
# I2C bus pool
# ============================================================

class BusPool:
    """
    One SMBus instance per Linux I2C bus.

    All access to a given bus is serialized.
    """

    def __init__(self):
        self._buses = {}
        self._locks = {}
        self._guard = threading.Lock()

    def _get(self, bus_number):
        with self._guard:

            if bus_number not in self._buses:
                self._buses[bus_number] = SMBus(
                    bus_number
                )

                self._locks[bus_number] = (
                    threading.RLock()
                )

            return (
                self._buses[bus_number],
                self._locks[bus_number]
            )

    def write_byte(
        self,
        bus_number,
        address,
        value
    ):
        bus, lock = self._get(bus_number)

        with lock:
            bus.write_byte(
                address,
                value & 0xFF
            )

    def read_byte(
        self,
        bus_number,
        address
    ):
        bus, lock = self._get(bus_number)

        with lock:
            return bus.read_byte(
                address
            )

    def close(self):
        with self._guard:

            for bus in self._buses.values():
                try:
                    bus.close()
                except Exception:
                    pass

            self._buses.clear()
            self._locks.clear()


# ============================================================
# PCF8574
# ============================================================

class PCF8574:
    """
    PCF8574 interface.

    HIGH:
        released / input

    LOW:
        actively sinking

    Our hardware uses:

        Button output:
            LOW  -> PC817 ON
            HIGH -> PC817 OFF

        LED input:
            PC817 ON -> pin pulled LOW
            PC817 OFF -> pin HIGH
    """

    def __init__(
        self,
        pool,
        bus_number,
        address
    ):
        self.pool = pool

        self.bus_number = bus_number
        self.address = address

        self.lock = threading.RLock()

        # Safe state:
        #
        # all button optocouplers OFF,
        # all input pins released.
        self.shadow = 0xFF

    @staticmethod
    def validate_pin(pin):
        if not isinstance(pin, int):
            raise PCPowerError(
                f"Invalid PCF8574 pin: {pin}"
            )

        if not 0 <= pin <= 7:
            raise PCPowerError(
                f"PCF8574 pin must be 0..7: {pin}"
            )

    def initialize(self):
        with self.lock:

            self.shadow = 0xFF

            self.pool.write_byte(
                self.bus_number,
                self.address,
                self.shadow
            )

            # Check that the chip responds.
            self.pool.read_byte(
                self.bus_number,
                self.address
            )

    def activate(self, pin):
        """
        Pull a pin LOW.
        """

        self.validate_pin(pin)

        with self.lock:

            self.shadow &= ~(
                1 << pin
            )

            self.pool.write_byte(
                self.bus_number,
                self.address,
                self.shadow
            )

    def release(self, pin):
        """
        Release a pin HIGH.
        """

        self.validate_pin(pin)

        with self.lock:

            self.shadow |= (
                1 << pin
            )

            self.pool.write_byte(
                self.bus_number,
                self.address,
                self.shadow
            )

    def read_pin(self, pin):
        """
        Read a released PCF8574 pin.
        """

        self.validate_pin(pin)

        with self.lock:

            if not (
                self.shadow
                & (1 << pin)
            ):
                raise PCPowerError(
                    f"Attempted to read P{pin}, "
                    "but it is currently driven LOW"
                )

            value = self.pool.read_byte(
                self.bus_number,
                self.address
            )

        return bool(
            value & (1 << pin)
        )


# ============================================================
# Machine
# ============================================================

class Machine:

    def __init__(
        self,
        name,
        expander,
        pins,
        settings
    ):
        self.name = name
        self.expander = expander

        self.power_pin = (
            pins["power_button"]
        )

        self.reset_pin = (
            pins.get("reset_button")
        )

        self.power_led_pin = (
            pins["power_led"]
        )

        self.hdd_led_pin = (
            pins.get("hdd_led")
        )

        self.settings = settings

        # Only one power operation per machine.
        self.operation_lock = (
            threading.Lock()
        )

    # ========================================================
    # Inputs
    # ========================================================

    def _active_low(self, pin):
        return not self.expander.read_pin(
            pin
        )

    def is_on(self):
        """
        Debounced power LED read.
        """

        samples = max(
            1,
            int(
                self.settings[
                    "status_samples"
                ]
            )
        )

        sample_delay = (
            int(
                self.settings[
                    "status_sample_ms"
                ]
            )
            / 1000.0
        )

        active = 0

        for index in range(samples):

            if self._active_low(
                self.power_led_pin
            ):
                active += 1

            if index < samples - 1:
                time.sleep(
                    sample_delay
                )

        return active > samples // 2

    def hdd_active(self):
        if self.hdd_led_pin is None:
            return None

        return self._active_low(
            self.hdd_led_pin
        )

    def status(self):
        return {
            "name": self.name,
            "power": (
                "on"
                if self.is_on()
                else "off"
            ),
            "hdd": (
                None
                if self.hdd_led_pin is None
                else (
                    "active"
                    if self.hdd_active()
                    else "idle"
                )
            )
        }

    # ========================================================
    # Button handling
    # ========================================================

    def _press(
        self,
        pin,
        duration_ms
    ):
        self.expander.activate(
            pin
        )

        try:
            time.sleep(
                duration_ms / 1000.0
            )

        finally:
            # Never leave a physical button pressed.
            self.expander.release(
                pin
            )

    def press_power(
        self,
        duration_ms=None
    ):
        if duration_ms is None:
            duration_ms = int(
                self.settings[
                    "button_press_ms"
                ]
            )

        self._press(
            self.power_pin,
            duration_ms
        )

    def reset(self):
        if self.reset_pin is None:
            raise PCPowerError(
                f"{self.name}: reset is not configured"
            )

        if not self.is_on():
            raise PCPowerError(
                f"{self.name}: machine is off"
            )

        with self.operation_lock:
            self._press(
                self.reset_pin,
                int(
                    self.settings[
                        "button_press_ms"
                    ]
                )
            )

        return self.status()

    # ========================================================
    # Wait for hardware state
    # ========================================================

    def wait_for_state(
        self,
        wanted,
        timeout
    ):
        deadline = (
            time.monotonic()
            + float(timeout)
        )

        while (
            time.monotonic()
            < deadline
        ):
            if self.is_on() == wanted:
                return True

            time.sleep(0.1)

        return self.is_on() == wanted

    # ========================================================
    # ON
    # ========================================================

    def power_on(self):
        with self.operation_lock:

            if self.is_on():
                return self.status()

            self.press_power()

            if not self.wait_for_state(
                True,
                self.settings[
                    "power_on_timeout_s"
                ]
            ):
                raise PCPowerError(
                    f"{self.name}: "
                    "power-on timeout"
                )

            return self.status()

    # ========================================================
    # Forced OFF
    # ========================================================

    def _force_off(self):

        hold_ms = int(
            self.settings[
                "force_off_hold_ms"
            ]
        )

        self.expander.activate(
            self.power_pin
        )

        try:
            deadline = (
                time.monotonic()
                + hold_ms / 1000.0
            )

            while (
                time.monotonic()
                < deadline
            ):

                if not self.is_on():
                    return True

                time.sleep(0.1)

        finally:
            self.expander.release(
                self.power_pin
            )

        return not self.is_on()

    # ========================================================
    # OFF
    # ========================================================

    def power_off(self):

        with self.operation_lock:

            if not self.is_on():
                return self.status()

            mode = str(
                self.settings[
                    "off_mode"
                ]
            ).lower()

            if mode == "force":

                if not self._force_off():
                    raise PCPowerError(
                        f"{self.name}: "
                        "forced power-off failed"
                    )

                return self.status()

            if mode == "short":

                self.press_power()

                if not self.wait_for_state(
                    False,
                    self.settings[
                        "graceful_off_timeout_s"
                    ]
                ):
                    raise PCPowerError(
                        f"{self.name}: "
                        "shutdown timeout"
                    )

                return self.status()

            if mode == "graceful_then_force":

                self.press_power()

                if self.wait_for_state(
                    False,
                    self.settings[
                        "graceful_off_timeout_s"
                    ]
                ):
                    return self.status()

                if not self._force_off():
                    raise PCPowerError(
                        f"{self.name}: "
                        "forced shutdown failed"
                    )

                return self.status()

            raise PCPowerError(
                f"{self.name}: "
                f"unknown off_mode {mode}"
            )


# ============================================================
# Controller
# ============================================================

class Controller:

    DEFAULTS = {
        "button_press_ms": 500,
        "power_on_timeout_s": 15,
        "force_off_hold_ms": 6000,
        "graceful_off_timeout_s": 30,
        "off_mode": "force",
        "status_samples": 3,
        "status_sample_ms": 30
    }

    def __init__(self, config):

        self.pool = BusPool()

        self.expanders = {}
        self.machines = {}

        self.used_pins = {}

        self._build(config)

    def _get_expander(
        self,
        bus,
        address
    ):
        key = (
            bus,
            address
        )

        if key not in self.expanders:

            self.expanders[key] = (
                PCF8574(
                    self.pool,
                    bus,
                    address
                )
            )

        return self.expanders[key]

    def _reserve_pin(
        self,
        machine,
        signal,
        bus,
        address,
        pin
    ):
        key = (
            bus,
            address,
            pin
        )

        if key in self.used_pins:

            raise PCPowerError(
                f"{machine}.{signal} uses "
                f"I2C-{bus} 0x{address:02x} "
                f"P{pin}, already used by "
                f"{self.used_pins[key]}"
            )

        self.used_pins[key] = (
            f"{machine}.{signal}"
        )

    def _build(self, config):

        defaults = dict(
            self.DEFAULTS
        )

        defaults.update(
            config.get(
                "defaults",
                {}
            )
        )

        machine_configs = (
            config.get(
                "machines",
                {}
            )
        )

        if not machine_configs:
            raise PCPowerError(
                "No machines configured"
            )

        for name, cfg in (
            machine_configs.items()
        ):

            bus = int(
                cfg.get(
                    "i2c_bus",
                    1
                )
            )

            address = parse_int(
                cfg[
                    "pcf8574_address"
                ]
            )

            pins = dict(
                cfg["pins"]
            )

            for required in (
                "power_button",
                "power_led"
            ):
                if required not in pins:
                    raise PCPowerError(
                        f"{name}: missing {required}"
                    )

            for signal, pin in list(
                pins.items()
            ):
                if pin is None:
                    continue

                pin = int(pin)

                PCF8574.validate_pin(
                    pin
                )

                pins[signal] = pin

                self._reserve_pin(
                    name,
                    signal,
                    bus,
                    address,
                    pin
                )

            settings = dict(
                defaults
            )

            settings.update(
                cfg.get(
                    "settings",
                    {}
                )
            )

            if settings["off_mode"] not in (
                "force",
                "short",
                "graceful_then_force"
            ):
                raise PCPowerError(
                    f"{name}: invalid off_mode"
                )

            expander = (
                self._get_expander(
                    bus,
                    address
                )
            )

            self.machines[name] = (
                Machine(
                    name,
                    expander,
                    pins,
                    settings
                )
            )

        # Initialize each physical chip once.
        for expander in (
            self.expanders.values()
        ):
            expander.initialize()

    def get(self, name):

        try:
            return self.machines[name]

        except KeyError:
            raise PCPowerError(
                f"Unknown machine: {name}"
            )

    def list_machines(self):

        return sorted(
            self.machines.keys()
        )

    def health(self):

        devices = {}

        healthy = True

        for (
            bus,
            address
        ), expander in (
            self.expanders.items()
        ):

            name = (
                f"i2c-{bus}:"
                f"0x{address:02x}"
            )

            try:
                value = (
                    self.pool.read_byte(
                        bus,
                        address
                    )
                )

                devices[name] = {
                    "ok": True,
                    "value": (
                        f"0x{value:02x}"
                    )
                }

            except Exception as error:

                healthy = False

                devices[name] = {
                    "ok": False,
                    "error": str(error)
                }

        return {
            "ok": healthy,
            "devices": devices
        }

    def close(self):
        self.pool.close()