#!/usr/bin/env python3

import subprocess
import os
import json
from pathlib import Path

NET_INTERFACE = "eth0"
MOBILE_ATLAS_MAIN_DIR = "/etc/mobileatlas/"
GIT_DIR = "/home/pi/mobile-atlas/"


def get_mac_addr(net_interface=NET_INTERFACE):
    """Return the mac address from sys filesystem"""
    if not os.path.exists("/sys/class/net/" + NET_INTERFACE + "/address"):
        return None
    with open("/sys/class/net/" + NET_INTERFACE + "/address") as f:
        return f.readline().rstrip()

def get_uptime():
    # Uptime from proc (in seconds)
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        return uptime_seconds

def get_temperature():
    # CPU Temperature from sys
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        temp = float(f.readline())/1000
        return temp

def get_network_info():
    try:
        network_info = json.loads(subprocess.check_output(["ip", "-4", "-s", "-j", "a"]))
        return network_info    
    except Exception:
        pass

def get_git_head(git_dir):
    # git HEAD commit
    # There are other options to do this (read file), but lets take the subprocess
    # GIT_HEAD = "/home/pi/mobile-atlas/.git/refs/heads/master"
    # with open(GIT_HEAD, 'r') as f:
    #     head = f.readline()
    #     information['head'] = head[:8]
    try:
        git_head = subprocess.check_output(["git", "-C", git_dir, "rev-parse", "--short", "HEAD"]).decode()
        return git_head
    except Exception:
        pass

def get_system_information(git_dir=GIT_DIR):
    """Load system information from different sources"""
    information = dict()

    information['uptime'] = get_uptime()

    information['temp'] = get_temperature()

    git_head = get_git_head(git_dir)
    if git_head:
        information['head'] = git_head
    
    network_info = get_network_info()
    if network_info:
        information['network'] = network_info

    return information


def write_activity_log(id, activity_name, start, stop="", target_dir=MOBILE_ATLAS_MAIN_DIR, filename="activities.csv"):
    path = Path(target_dir / filename)
    path.touch()
    with path.open('a') as f:
        f.write(f"{id},{activity_name},{start},{stop}\n")


def load_token(token_dir):
    """Load the stored token or None"""
    if not os.path.exists(token_dir + "/token"):
        return None
    with open(token_dir + "/token") as f:
        token = f.readline().rstrip()
        return token

def store_token(token_dir, token):
    """Store the token in file"""
    if not os.path.exists(token_dir):
        os.makedirs(token_dir)

    with open(token_dir + "/token", "w") as f:
        f.write(f"{token}\n")