#!/bin/bash

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