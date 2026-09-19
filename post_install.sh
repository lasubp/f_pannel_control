#!/bin/bash

chmod 755 \
    /opt/pcpower/pcpowerd.py \
    /opt/pcpower/pcpowerctl.py

ln -s \
    /opt/pcpower/pcpowerctl.py \
    /usr/local/bin/pcpowerctl

apt update

apt install -y \
    python3 \
    python3-venv \
    i2c-tools

python3 -m venv \
    /opt/pcpower/venv

/opt/pcpower/venv/bin/pip \
    install smbus2
