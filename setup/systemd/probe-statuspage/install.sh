#!/bin/bash

#sudo mkdir -p /usr/local/lib/probe-statuspage/
#sudo ln -s probe-statuspage.py /usr/local/lib/probe-statuspage/probe-statuspage.py
#sudo ln -s venv/ /usr/local/lib/probe-statuspage/venv/
sudo ln -s . /lib/systemd/system/probe-statuspage
sudo cp probe-statuspage.service /lib/systemd/system/

sudo systemctl enable probe-statuspage