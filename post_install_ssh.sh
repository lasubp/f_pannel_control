#!/bin/bash

# Setup machine
SSH_MASHINE=dietpi

ssh root@$SSH_MACHINE 'bash -s' < post_install.sh
