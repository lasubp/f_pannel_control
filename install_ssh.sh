#!/bin/bash

# Setup machine
SSH_MASHINE=dietpi

# create directories
ssh root@$SSH_MACHINE 'mkdir /etc/pcpower'
ssh root@$SSH_MACHINE 'mkdir /opt/pcpower'

# Copy filed to desired dirs
scp ./src/config.json $SSH_MACHINE:/etc/pcpower/config.json
scp ./src/pcpower_core.py $SSH_MACHINE:/opt/pcpower/pcpower_core.py
scp ./src/pcpowerd.py $SSH_MACHINE:/opt/pcpower/pcpowerd.py
scp ./src/pcpowerctl.py $SSH_MACHINE:/opt/pcpower/pcpowerctl.py
scp ./src/pcpowerd.service $SSH_MACHINE:/etc/systemd/system/pcpowerd.service
