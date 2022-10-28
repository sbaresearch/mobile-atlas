#!/usr/bin/env python3

"""This script automatically configures wireguard after startup"""

import requests
import subprocess
import os

#hack to add probe utlities module
import sys
from pathlib import Path 
PROBE_UTILITIES_DIR = str(Path(__file__).parent.parent.resolve())
sys.path.append(PROBE_UTILITIES_DIR)
import probe_utilities


WIREGUARD_DIR = "/etc/wireguard"
REGISTER_URL = "https://mam.mobileatlas.eu/wireguard/register"
NET_INTERFACE = "eth0"

# WIREGUARD_DIR = "/tmp/wireguard"
# REGISTER_URL = "http://localhost:5000/wireguard/register"
# NET_INTERFACE = "wlp2s0"

def get_or_create_wireguard_key(wireguard_dir):
    """
    Either read the keys or create new one with "wg genkey"
    """
    # TODO check if public key is also >0 bytes
    if not os.path.exists(wireguard_dir + "/client_wg0_private.key") or not os.path.exists(wireguard_dir + "/client_wg0_public.key"):
        print("Create new keys")
        subprocess.Popen(f"wg genkey > {wireguard_dir}/client_wg0_private.key", shell=True).wait()
        subprocess.Popen(f"wg pubkey < {wireguard_dir}/client_wg0_private.key > {wireguard_dir}/client_wg0_public.key",
                         shell=True).wait()

    with open(wireguard_dir + "/client_wg0_public.key") as pubf, open(wireguard_dir + "/client_wg0_private.key") as privf:
        return {"public": pubf.readline().rstrip(), "private": privf.readline().rstrip()}


def save_wireguard_config(wireguard_dir, private, ip, endpoint, publickey_endpoint, allowed_ips, dns):
    """
    Generate the config, however it will overwrite any existing wg0.conf
    """
    with open(wireguard_dir + "/wg0.conf", "w") as cf:
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

    mac = probe_utilities.get_mac_addr(NET_INTERFACE)
    print(f"Got {mac} for {NET_INTERFACE}")

    # TODO check if wireguard is installed

    keys = get_or_create_wireguard_key(WIREGUARD_DIR)
    print(f"Got publickey {keys['public']}")

    res = requests.post(REGISTER_URL, data={'mac': mac, 'publickey': keys['public']})
    if res.status_code == 200:
        j = res.json()
        ip = j['ip']
        endpoint = j['endpoint']
        endpoint_publickey = j['endpoint_publickey']
        allowed_ips = j['allowed_ips']
        dns = j['dns']

        # TODO check values: ip/endpoint/endpoint_publickey/allowed_ips
        print("Registered")

        probe_utilities.save_wireguard_config(WIREGUARD_DIR, keys['private'], ip, endpoint, endpoint_publickey, allowed_ips, dns)
        print("Stored config")

    else:
        print("Error", res.status_code, res.text)


if __name__ == '__main__':
    main()
