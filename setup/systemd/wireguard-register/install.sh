#!/bin/bash

sudo mkdir -p /usr/local/lib/wireguard-register/
sudo cp wireguard-register.py /usr/local/lib/wireguard-register/
sudo cp wireguard-register.service /lib/systemd/system/

sudo systemctl enable wireguard-register