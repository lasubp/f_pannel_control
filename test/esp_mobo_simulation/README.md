# Simulate PC F-pannel with ESP32-C3

## Purpose

Testing purpose, while deweloping remote front pannel controller. No need to use chunky PC.

## How does it works

Connect remote front pannel controller to ESP32 GPIO pins, access ESP32 seriall and you can recive and analize inputs and outputs of simulated front pannel without actual PC.
Remote controller wouldnt see any difference betwean CP and this ESP23 sinulator.
No additional hardware needed/ But I you want, you can connect physical buttons and LEDs to the same pins on EPS32

## Setup

Connect f-pannel power button, reset button and power LED, HDD LED to the esp32 GPIO.

```text
    CONTROLLER                         FAKE PC

 PCF8574 + PC817                        ESP32-C3

 PWR_SW --------------------------------> GPIO4
 RESET_SW ------------------------------> GPIO5

 PWR_LED <------------------------------- GPIO6
 HDD_LED <------------------------------- GPIO7
 ```
 
 If script was modified, change pins accordingly.
 
 Connect ESP32 to the PC, upload sketch.
 In the Arduino IDE open `Serial Monitor` and set `New Line` and `115200 baud`.
 
## Monitiring commands
 
```
status
```

shows:

```
Power: ON/OFF
PWR_SW: PRESSED/RELEASED
RESET_SW: PRESSED/RELEASED
PWR_LED: ON/OFF
HDD_LED: ON/OFF
```

Manually fake PC power on:

```
on
```

Manually fake PC power off:

```
off
```

Test HDD:

```
hdd on
```

or:

```
hdd off
```

or:

```
hdd auto
```
