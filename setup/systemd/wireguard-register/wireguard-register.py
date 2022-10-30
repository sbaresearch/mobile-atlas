#!/usr/bin/env python3

"""This script automatically configures wireguard after startup"""

import requests
import subprocess
from os import path

WIREGUARD_DIR = "/etc/wireguard"
REGISTER_URL = "https://mam.mobileatlas.eu/wireguard/register"
NET_INTERFACE = "eth0"

# WIREGUARD_DIR = "/tmp/wireguard"
# REGISTER_URL = "http://localhost:5000/wireguard/register"
# NET_INTERFACE = "wlp2s0"


def get_mac_addr():
    """
    Return the mac address from sys filesystem
    """
    with open("/sys/class/net/"+NET_INTERFACE+"/address") as f:
        return f.readline().rstrip()


def get_or_create_wireguard_key():
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
    with open(WIREGUARD_DIR + "/wg0.conf", "w") as cf:
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

    mac = get_mac_addr()
    print(f"Got {mac} for {NET_INTERFACE}")

    # TODO check if wireguard is installed

    keys = get_or_create_wireguard_key()
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

        save_wireguard_config(keys['private'], ip, endpoint, endpoint_publickey, allowed_ips, dns)
        print("Stored config")

    else:
        print("Error", res.status_code, res.text)


if __name__ == '__main__':
    main()

