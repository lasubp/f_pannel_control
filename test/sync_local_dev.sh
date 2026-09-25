#!/bin/bash

# Setup machine
SSH_MASHINE=dietpi
SSH_USER=root
SRC=../src

rsync -v ${SRC}/config.json ${SSH_USER}@${SSH_MASHINE}:/etc/pcpower/config.json
rsync -v ${SRC}/pcpower_core.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpower_core.py
rsync -v ${SRC}/pcpowerd.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpowerd.py
rsync -v ${SRC}/pcpowerctl.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpowerctl.py
rsync -v ${SRC}/pcpowerd.service ${SSH_USER}@${SSH_MASHINE}:/etc/systemd/system/pcpowerd.service
rsync -v ${SRC}/config.yaml ${SSH_USER}@${SSH_MASHINE}:/etc/pcpower/config.yaml
rsync -Rv ../addons ${SSH_USER}@${SSH_MASHINE}:/root
