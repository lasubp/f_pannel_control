# Developed and tested on

SBC: Raspberry PI 3b
OS: DietPI (based on Debian 13 "Trixie")

# Prerequisits

Enable GPIO ans I2C

## Manual instalallation

Copy files from `src` directory to appopriate locations:
config: `/etc/pcpower/config.yaml`
core module: `/opt/pcpower/pcpower_core.py`
daemon: `/opt/pcpower/pcpowerd.py`
cli client: `/opt/pcpower/pcpowerctl.py`
system service: `/etc/systemd/system/pcpowerd.service`

Set permissions for executables: 
```bash
chmod 755 \
    /opt/pcpower/pcpowerd.py \
    /opt/pcpower/pcpowerctl.py
```

Create symlink for CLI tool:
```bash
ln -s \
    /opt/pcpower/pcpowerctl.py \
    /usr/local/bin/pcpowerctl
```

Install enviroment dependensies:

```bash
apt update

apt install -y \
    python3 \
    python3-venv \
    i2c-tools
```

Prepare python env
```bash
python3 -m venv \
    /opt/pcpower/venv
```

Install external pyhon dependencies in env
```bash
/opt/pcpower/venv/bin/pip \
    install smbus2 pyyaml
```

Check expanders i2c adresses
```bash
i2cdetect -y 1
```

### Create dedicated user

```bash
groupadd --system pcpower
```

```bash
useradd \
    --system \
    --gid pcpower \
    --home-dir /opt/pcpower \
    --shell /usr/sbin/nologin \
    pcpower
```

```bash
usermod \
    -aG i2c \
    pcpower
```

###  Enable system service
```bash
systemctl daemon-reload
systemctl enable --now pcpowerd
```

Check it
```bash
systemctl status pcpowerd
```

Logs
```bash
journalctl -u pcpowerd -f
```

## Automated instalation

There automated script `install.sh`, that will place all files in their paces and configure enviroment.
Only thing you need is to run it with `root` or `sudo` privileges.

If you root user:
```bash
./install.sh
```

Or if you not but have sudo priviliges
```bash
sudo ./install.sh
```
# Configuration

To fing out pcf adresses use next command:

```bash
i2cdetect -y 1
```

Or calculate manually by swithed jumpers A0, A1, A2 on PCF8574 foard.

Thise tool accept config files in `yaml` and `json` formats.
Default config location at `/etc/pcpower/config.yaml`.
I you want to use custom config location. It can  be set by daemon using :

```bash
pcpowerd.py --config /path/to/config.yaml
```

It will create new servise.
If you actually need to make that config permanent, only way to do so is to set that parameter in system service file `pcpowerd.service`.

## Config file examles

YAML:

```yaml
defaults:
  button_press_ms: 500
  force_off_hold_ms: 6000
  graceful_off_timeout_s: 30
  off_mode: force
  power_on_timeout_s: 15
  status_sample_ms: 30
  status_samples: 3

machines:
  pc1:
    i2c_bus: 1
    pcf8574_address: '0x20'
    pins:
      hdd_led: 3
      power_button: 0
      power_led: 2
      reset_button: 1
  pc2:
    i2c_bus: 1
    pcf8574_address: '0x21'
    pins:
      hdd_led: 3
      power_button: 0
      power_led: 2
      reset_button: 1
```


JSON:

```json
{
  "defaults": {
    "button_press_ms": 500,
    "power_on_timeout_s": 15,
    "force_off_hold_ms": 6000,
    "graceful_off_timeout_s": 30,
    "off_mode": "force",
    "status_samples": 3,
    "status_sample_ms": 30
},
  
"machines": {
  "pc1": {
    "i2c_bus": 1,
    "pcf8574_address": "0x20",
    "pins": {
      "power_button": 0,
      "reset_button": 1,
      "power_led": 2,
      "hdd_led": 3
    }
  },
  "pc2": {
    "i2c_bus": 1,
    "pcf8574_address": "0x21",
    "pins": {
      "power_button": 0,
      "reset_button": 1,
      "power_led": 2,
      "hdd_led": 3
      }
    }
      
  }
}
```

Ammoun of machines can be easely scled by adding new blocks to config and changing `pcf8574_address`.
Supported up to **8** `pcf8574` addresses, that is **maximmum amount i2c buss accept**.
But on each `pc` we can also **cofigure pcf8574 pins**. So, having that each of them have **8** pins but we are using only **4**, amoun of controlled PCs can scale **2x**, giwing us **16** in total.
Also if you don't want to use `reset button` and/or `HDD LED`, ypu **can remove them from configurtion**. It will free that pins for even more PCs.

*Parameters for `power_button` and `power_led` are **required**.*

# Basic electronical scheme

## Reqired components:

- **PCF8574** I2C expander
- For one button:
	- Optocomputer **PC817** - 1x
	- Resistor **390R** - 1x
- For one LED:
	- Optocomputer **PC817** - 1x
	- Resistor **390R** - 1x
	- Resistor **10K** - 1x

## Scheme drawind

Basic scheme of component connections for one button and one LED

![[schema.png]]

# Usage

There machine name used is `pc1`. Change it accordingly to your config

| Command                                      | What it does                                                                                                         |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `pcpowerctl list`                            | Lists configured machine names.                                                                                      |
| `pcpowerctl health`                          | Checks whether each configured PCF8574 responds over I²C.                                                            |
| `pcpowerctl status pc1`                      | Reads the power LED and reports whether the PC is on or off; also reports HDD LED state if configured.               |
| `pcpowerctl inputs pc1`                      | Shows the power LED and HDD LED as `ON`, `OFF`, or `N/A`.                                                            |
| `pcpowerctl raw pc1`                         | Shows the raw byte and all eight pin levels from the PCF8574.                                                        |
| `pcpowerctl press power pc1`                 | Presses the power button for the configured button duration, without checking the LED or waiting for a state change. |
| `pcpowerctl press reset pc1`                 | Presses the reset button, if a reset pin is configured.                                                              |
| `pcpowerctl press power pc1 --duration 1000` | Presses the power button for 1000 milliseconds. The same option works with `reset`.                                  |
| `pcpowerctl on pc1`                          | If the power LED says the PC is off, presses power and waits for it to turn on.                                      |
| `pcpowerctl off pc1`                         | If the power LED says the PC is on, shuts it down according to the configured `off_mode`.                            |
| `pcpowerctl reset pc1`                       | Resets the PC if it is on and a reset button is configured.                                                          |
| `pcpowerctl reload`                          | Reloads the daemon’s configuration file without restarting the service.                                              |

## Additional parameters

Print structured output in JSON format:

```
pcpowerctl --json status pc1
```

```
{
  "ok": true,
  "result": {
    "name": "pc1",
    "power": "on",
    "hdd": "idle"
  }
}
```

Set socket path:

```
pcpowerctl --socket /run/pcpower/control.sock list
```

*Used **only** when socket path was manually set with daemon itself.*
Default socket path is /run/pcpower/control.sock

## The daemon itself accepts:

```
pcpowerd.py --config /etc/pcpower/config.yaml --socket /run/pcpower/control.sock
pcpowerd.py --config /etc/pcpower/config.yaml --check
```

`--config` - point to dondefault config file location.
`--check` - starts the controller, prints its health result, and exits. For ordinary use, the daemon runs through `pcpowerd.service`, and you issue commands with `pcpowerctl`.
`--socket` - can set don default socket path. May be ysed for sepatate testing socket. If set, `pcpowerctl` also must use same parameter and path to use that socket.

# The local protocol

The daemon listens on a Unix socket, normally `/run/pcpower/control.sock`. A client sends one JSON object followed by a newline. The daemon replies with one JSON object followed by a newline. A connection can carry multiple requests.

## Responses

A successful response has this form:

```json
{"ok":true,"result":{...}}
```

A failed response has this form:

```json
{"ok":false,"error":{"message":"error description"}}
```

# Available daemon request actions

|Request|What it does|
|---|---|
|`{"action":"list"}`|List configured machines.|
|`{"action":"health"}`|Check configured I²C devices.|
|`{"action":"status","machine":"pc1"}`|Report power state and optional HDD activity.|
|`{"action":"inputs","machine":"pc1"}`|Read the power LED and optional HDD LED.|
|`{"action":"raw","machine":"pc1"}`|Read the PCF8574 byte and individual pins.|
|`{"action":"on","machine":"pc1"}`|Turn the machine on if it reads as off, then wait for the power LED.|
|`{"action":"off","machine":"pc1"}`|Turn the machine off using its configured `off_mode`.|
|`{"action":"reset","machine":"pc1"}`|Press reset if the machine is on and a reset pin is configured.|
|`{"action":"press","machine":"pc1","button":"power"}`|Press a button without checking or waiting for the machine’s state. `button` may be `"power"` or `"reset"`.|
|`{"action":"reload"}`|Reload the daemon’s configured file from disk.|

For `press`, you can optionally specify a positive duration in milliseconds:

```json
{"action":"press","machine":"pc1","button":"power","duration_ms":1000}
```

## Example results

A `status`, `on`, `off`, or `reset` request returns a status result such as:

```json
{"ok":true,"result":{"name":"pc1","power":"on","hdd":"idle"}}
```

`power` is `"on"` or `"off"`. If no HDD LED is configured, `hdd` is `null`.

Other results include:

```json
{"ok":true,"result":{"machines":["pc1"]}}
```

```json
{"ok":true,"result":{"name":"pc1","power_led":true,"hdd_led":null}}
```

```json
{"ok":true,"result":{"name":"pc1","button":"power","duration_ms":1000}}
```

```json
{"ok":true,"result":{"reloaded":true,"machines":["pc1"]}}
```

These examples show `list`, `inputs`, `press`, and `reload`, respectively. `health` returns an `ok` value and a `devices` object **inside** `result`; `raw` returns the machine name, bus, address, byte in hexadecimal and binary, and pin levels.

## Resulting architecture

```
                 hardware config
                       |
                       v
                   pcpowerd
                       |
             /run/pcpower/control.sock
                       |
       +---------------+----------------+
       |               |                |
 pcpowerctl       maas-power       pcpower-web
                    later              later
                                        |
                                   browser/API
```

The most important architectural rule is: **only `pcpowerd` touches `/dev/i2c-*`.** Everything else talks to `pcpowerd`. That prevents race conditions where MAAS, a WebUI, and a CLI each maintain different PCF8574 output state and accidentally overwrite one another.
