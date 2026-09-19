#!/bin/bash

# create directories
mkdir /etc/pcpower
mkdir /opt/pcpower

# Copy filed to desired dirs
cp ./src/config.json /etc/pcpower/config.json
cp ./src/pcpower_core.py /opt/pcpower/pcpower_core.py
cp ./src/pcpowerd.py /opt/pcpower/pcpowerd.py
cp ./src/pcpowerctl.py /opt/pcpower/pcpowerctl.py
cp ./src/pcpowerd.service /etc/systemd/system/pcpowerd.service
