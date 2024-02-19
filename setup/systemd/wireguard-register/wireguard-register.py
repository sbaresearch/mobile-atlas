#!/usr/bin/env python3

"""This script automatically configures wireguard after startup"""

import requests
import secrets
import base64
import subprocess
import sys
from os import path

# TODO set correct path
#PROBE_UTILITIES = "/home/pf/Documents/mobile-atlas-merge/setup/systemd/probe_utilities.py"
PROBE_UTILITIES = "/home/pf/Documents/mobile-atlas-merge/setup/systemd/"
sys.path.append(PROBE_UTILITIES)

import probe_utilities as probe_util

WIREGUARD_DIR = "/etc/wireguard"
#API_ENDPOINT = "https://mam.mobileatlas.eu"
API_ENDPOINT = "http://localhost:5000"
TOKEN_REG_URL = f"{API_ENDPOINT}/tokens/register"
REGISTER_URL = f"{API_ENDPOINT}/wireguard/register"
NET_INTERFACE = "eth0"

# WIREGUARD_DIR = "/tmp/wireguard"
# REGISTER_URL = "http://localhost:5000/wireguard/register"
# NET_INTERFACE = "wlp2s0"

def _get_or_create_wireguard_token():
    return "vwMzQbmpvo0asJ0+GFtk6hC6Vd+T3LtnYYxFkCJkKRk="

def get_or_create_mam_token():
    token_path = WIREGUARD_DIR + "/token"

    if not path.exists(token_path):
        print("Creating a new MAM token")
        token = base64.b64encode(secrets.token_bytes(32)).decode()

        with open(token_path, "x") as f:
            f.write(token)

        return token
    else:
        with open(token_path) as f:
            return f.readline()

def get_or_create_wireguard_key():
    return {"public": "KJ+OCAwcvyz4rILS0tXMPrVYloE/S5SOWz+eujAYJHs=", "private": "wGHkux2e+A9BPPqDvKZUgYuppzCuL/L/J/yp84uHF3o="}

def _get_or_create_wireguard_key():
    """
    Either read the keys or create new one with "wg genkey"
    """
    # TODO check if public key is also >0 bytes
    if not path.exists(WIREGUARD_DIR + "/client_wg0_private.key") or not path.exists(WIREGUARD_DIR + "/client_wg0_public.key"):
        print("Create new keys")
        subprocess.Popen(f"wg genkey > {WIREGUARD_DIR}/client_wg0_private.key", shell=True).wait()
        subprocess.Popen(f"wg pubkey < {WIREGUARD_DIR}/client_wg0_private.key > {WIREGUARD_DIR}/client_wg0_public.key",
                         shell=True).wait()

    with open(WIREGUARD_DIR + "/client_wg0_public.key") as pubf, open(WIREGUARD_DIR + "/client_wg0_private.key") as privf:
        return {"public": pubf.readline().rstrip(), "private": privf.readline().rstrip()}


def save_wireguard_config(private, ip, endpoint, publickey_endpoint, allowed_ips, dns):
    """
    Generate the config, however it will overwrite any existing wg0.conf
    """
    with open("/dev/tty", "w") as cf:
    #with open(WIREGUARD_DIR + "/wg0.conf", "w") as cf:
        cf.write(f"[Interface]\n")
        cf.write(f"Address = {ip}/32\n")
        cf.write(f"PrivateKey = {private}\n")
        cf.write(f"DNS = {dns}\n")
        cf.write(f"\n")
        cf.write(f"[Peer]\n")
        cf.write(f"Endpoint = {endpoint}\n")
        cf.write(f"PublicKey = {publickey_endpoint}\n")
        cf.write(f"AllowedIPs = {allowed_ips}\n")
        cf.write(f"\n")
        cf.write(f"PersistentKeepalive = 25\n")


def main():
    print("Startup Registering")

    mac = probe_util.get_mac_addr(NET_INTERFACE)
    print(f"Got {mac} for {NET_INTERFACE}")

    # TODO check if wireguard is installed

    token = probe_util.load_or_create_token()

    res = probe_util.register_token(token, mac=mac)

    if res.status_code != 200:
        print("Error", res.status_code, res.text)
        return

    keys = get_or_create_wireguard_key()
    print(f"Got publickey {keys['public']}")

    res = requests.post(
            REGISTER_URL,
            data={"publickey": keys["public"], "mac": mac},
            headers={"Authorization": f"Bearer {token}"},
            )

    if res.status_code != 200:
        print("Error", res.status_code, res.text)
        return

    j = res.json()
    ip = j['ip']
    endpoint = j['endpoint']
    endpoint_publickey = j['endpoint_publickey']
    allowed_ips = j['allowed_ips']
    dns = j['dns']

    # TODO check values: ip/endpoint/endpoint_publickey/allowed_ips
    print("Registered")

    save_wireguard_config(keys['private'], ip, endpoint, endpoint_publickey, allowed_ips, dns)
    print("Stored config")


if __name__ == '__main__':
    main()

