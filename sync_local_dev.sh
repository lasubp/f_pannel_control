#!/bin/bash

# Setup machine
SSH_MASHINE=dietpi
SSH_USER=root

rsync -R "ssh -i" "./src/config.json" "$SSH_MASHINE:/etc/pcpower/config.json"
rsync -R "ssh -i" "./src/pcpower_core.py" "$SSH_MASHINE:/opt/pcpower/pcpower_core.py"
rsync -R "ssh -i" "./src/pcpowerd.py" "$SSH_MASHINE:/opt/pcpower/pcpowerd.py"
rsync -R "ssh -i" "./src/pcpowerctl.py" "$SSH_MASHINE:/opt/pcpower/pcpowerctl.py"
rsync -R "ssh -i" "./src/pcpowerd.service" "$SSH_USER@$SSH_MASHINE:/etc/systemd/system/pcpowerd.service"