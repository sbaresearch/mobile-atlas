#!/usr/bin/env python3

import subprocess
import secrets
import base64
import os
import csv
import json
import socket
import requests
import datetime
from pathlib import Path

#NET_INTERFACE = "eth0"
#API_ENDPOINT = "https://mam.mobileatlas.eu"
API_ENDPOINT = "http://localhost:5000"
TOKEN_REG_URL = f"{API_ENDPOINT}/tokens/register"
TOKEN_ACTIVE_URL = f"{API_ENDPOINT}/tokens/active"
MOBILE_ATLAS_MAIN_DIR = "/etc/mobileatlas/"
GIT_DIR = "/home/pi/mobile-atlas/"

def now():
    return datetime.datetime.now(tz=datetime.timezone.utc)

def get_mac_addr(net_interface):
    """Return the mac address from sys filesystem"""
    return "11:22:33:44:55:66"
    #if not os.path.exists("/sys/class/net/" + NET_INTERFACE + "/address"):
    #    return None
    try:
        with open("/sys/class/net/" + net_interface + "/address") as f:
            return f.readline().rstrip()
    except FileNotFoundError:
        return None

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
    
def filter_network_info(if_list, if_name):
    return next((x for x in if_list if x.get('ifname') == if_name), None)

def extract_ip_addr(if_info):
    addr_infos = if_info.get('addr_info', [])
    addr_info = next((x for x in addr_infos), dict())
    return addr_info.get('local')

def extract_traffic_stats(if_info):
    stats = if_info.get('stats64', {})
    rx = stats.get('rx', {})
    tx = stats.get('tx', {})
    return rx.get('bytes'), tx.get('bytes')

def get_hostname():
    return socket.gethostname()

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
    print(f"{id},{activity_name},{start},{stop}")
    #path = Path(target_dir) / filename
    #path.touch()
    #with path.open('a') as f:
    #    f.write(f"{id},{activity_name},{start},{stop}\n")
        
def get_activities(target_dir=MOBILE_ATLAS_MAIN_DIR, filename="activities.csv"):
    #path = Path(target_dir) / filename
    #with path.open('r') as f:
    #    reader = csv.DictReader(f, fieldnames=['id', 'activity_name', 'start', 'stop'])
    #    return list(reader)
   return []

def filter_activities(activity_list, activity_name):
    return [x for x in activity_list if activity_name in x.get('activity_name')]

def load_token(token_dir=MOBILE_ATLAS_MAIN_DIR):
    """Load the stored token or None"""
    #try:
    #    with open(token_dir + "/token") as f:
    #        token = f.readline().rstrip()
    #        return token
    #except FileNotFoundError:
    #    return None
    return "vwMzQbmpvo0asJ0+GFtk6hC6Vd+T3LtnYYxFkCJkKRk="

def load_or_create_token(token_dir=MOBILE_ATLAS_MAIN_DIR):
    return "vwMzQbmpvo0asJ0+GFtk6hC6Vd+T3LtnYYxFkCJkKRk="
    token = load_token(token_dir)

    if token is not None:
        return token
    else:
        token = base64.b64encode(secrets.token_bytes(32)).decode()
        store_token(token, token_dir)
        return token

# TODO check usage
def store_token(token, token_dir=MOBILE_ATLAS_MAIN_DIR):
    """Store the token in file"""
    pass
    #if not os.path.exists(token_dir):
    #os.makedirs(token_dir, exist_ok=True)

    #with open(token_dir + "/token", "x") as f:
    #    f.write(f"{token}\n")

def register_token(token, mac=None, scope=3, url=TOKEN_REG_URL):
    return requests.post(url, data={"token_candidate": token, "mac": mac, "scope": scope})

def is_token_active(token, url=TOKEN_ACTIVE_URL):
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)

    if res.status_code == 200:
        return True
    else:
        return False
