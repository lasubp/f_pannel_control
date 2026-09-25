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

# Set permissions for executables
chmod 755 \
    /opt/pcpower/pcpowerd.py \
    /opt/pcpower/pcpowerctl.py

# Create symlink for CLI tool
ln -s \
    /opt/pcpower/pcpowerctl.py \
    /usr/local/bin/pcpowerctl

# Install enviroment dependensies
apt update


apt install -y \
    python3 \
    python3-venv \
    i2c-tools

# Prepare python env
python3 -m venv \
    /opt/pcpower/venv

# Install external pyhon dependencies in env
/opt/pcpower/venv/bin/pip \
    install smbus2

# create dedicated user
groupadd --system pcpower
useradd \
    --system \
    --gid pcpower \
    --home-dir /opt/pcpower \
    --shell /usr/sbin/nologin \
    pcpower
usermod \
    -aG i2c \
    pcpower

# Enable system servide
systemctl daemon-reload
systemctl enable --now pcpowerd