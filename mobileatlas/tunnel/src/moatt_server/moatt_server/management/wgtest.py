#!/usr/bin/env python

import requests
import requests.auth
import secrets
import base64

API = "http://localhost:5000"
WGAPI = f"{API}/wireguard"
#TOKEN = base64.b64encode(secrets.token_bytes(32)).decode()
TOKEN = "vwMzQbmpvo0asJ0+GFtk6hC6Vd+T3LtnYYxFkCJkKRk="
AUTH = requests.auth.HTTPBasicAuth("admin", "ioqfbasdf")
MAC = "11:22:33:44:55:66"

def register_token():
    payload = {"token_candidate": TOKEN, "mac": MAC, "scope": "3"}
    r = requests.post(f"{API}/tokens/register", data=payload)

    r.raise_for_status()

def activate_token():
    payload = {"token_candidate": TOKEN, "ip": "127.0.0.1", "name": "foo", "scope": "3"}
    r = requests.post(f"{API}/tokens/activate", data=payload, auth=AUTH)

    r.raise_for_status()

def deactivate_token():
    payload = {"token": TOKEN}
    r = requests.post(f"{API}/tokens/deactivate", data=payload, auth=AUTH)

    r.raise_for_status()

def register_wgtoken():
    payload = {"token_candidate": TOKEN, "mac": MAC}
    r = requests.post(f"{WGAPI}/tokens/register", data=payload)

    r.raise_for_status()

#def activate_token():
#    payload = {"token_candidate": TOKEN, "ip": "127.0.0.1"}
#    r = requests.post(f"{WGAPI}/token/activate", data=payload, auth=AUTH)
#
#    r.raise_for_status()

#def deactivate_token():
#    payload = {"token": TOKEN}
#    r = requests.post(f"{WGAPI}/token/deactivate", data=payload, auth=AUTH)
#
#    r.raise_for_status()

def register():
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    payload = {"publickey": key, "mac": MAC}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = requests.post(f"{WGAPI}/register", data=payload, headers=headers)

    r.raise_for_status()

    print(r.content)

def main():
    register_token()
    activate_token()
    #deactivate_token()
    #register()
    #deactivate_token()

if __name__ == "__main__":
    print(f"token: {TOKEN}")
    main()
