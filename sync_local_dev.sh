#!/bin/bash

# Setup machine
SSH_MASHINE=dietpi
SSH_USER=root

rsync -v ./src/config.json ${SSH_USER}@${SSH_MASHINE}:/etc/pcpower/config.json
rsync -v ./src/pcpower_core.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpower_core.py
rsync -v ./src/pcpowerd.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpowerd.py
rsync -v ./src/pcpowerctl.py ${SSH_USER}@${SSH_MASHINE}:/opt/pcpower/pcpowerctl.py
rsync -v ./src/pcpowerd.service ${SSH_USER}@${SSH_MASHINE}:/etc/systemd/system/pcpowerd.service