#!/usr/bin/python3
import json
import os
import sys
import time
import requests
import subprocess
from datetime import datetime, timedelta

MAM_URL = "https://mam.mobileatlas.eu"
NET_INTERFACE = "eth0"
TOKEN_STORAGE_DIR = "/etc/mobileatlas/"
GIT_DIR = "/home/pi/mobile-atlas/"
# Todo improve test/prod config

# Seconds to wait for after Exception
RETRY_INTERVAL = 60
# Seconds in between System Information Updates
SYSTEM_INFO_UPDATE_INTERVAL = 3600
# Timeout for Requests, according to LongPollingValue
TIMEOUT = 90


def token_header():
    """Return the Authorization headers for Requests"""
    if state['token']:
        return {"Authorization": f"Bearer {state.get('token')}"}
    else:
        return {}


def get_mac_addr():
    """Return the mac address from sys filesystem"""
    if not os.path.exists("/sys/class/net/" + NET_INTERFACE + "/address"):
        return None
    with open("/sys/class/net/" + NET_INTERFACE + "/address") as f:
        return f.readline().rstrip()


def load_token():
    """Load the stored token or None"""
    if not os.path.exists(TOKEN_STORAGE_DIR + "/token"):
        return None
    with open(TOKEN_STORAGE_DIR + "/token") as f:
        token = f.readline().rstrip()
        return token


def store_token(token):
    """Store the token in file"""
    if not os.path.exists(TOKEN_STORAGE_DIR):
        os.makedirs(TOKEN_STORAGE_DIR)

    with open(TOKEN_STORAGE_DIR + "/token", "w") as f:
        f.write(f"{token}\n")


def get_system_information():
    """Load system information from different sources"""
    information = dict()

    # Uptime from proc (in seconds)
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        information['uptime'] = uptime_seconds

    # CPU Temperature from sys
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        temp = float(f.readline())/1000
        information['temp'] = temp

    # git HEAD commit
    # There are other options to do this (read file), but lets take the subprocess
    # GIT_HEAD = "/home/pi/mobile-atlas/.git/refs/heads/master"
    # with open(GIT_HEAD, 'r') as f:
    #     head = f.readline()
    #     information['head'] = head[:8]

    try:
        information['head'] = subprocess.check_output(["git", "-C", GIT_DIR, "rev-parse", "--short", "HEAD"]).decode()
    except Exception:
        pass

    # Network information from ip "-4 -s -j a"
    try:
        information['network'] = json.loads(subprocess.check_output(["ip", "-4", "-s", "-j", "a"]))
    except Exception:
        pass

    return information


def authenticate():
    """
    Authenticate with Token or MAC address
    """

    # Check if token exists
    if state['token']:
        r = requests.post(MAM_URL + '/probe/register',
                          data={'mac': state['mac']},
                          headers=token_header(),
                          timeout=TIMEOUT)
    # Otherwise request token with MAC
    elif state['mac']:
        r = requests.post(MAM_URL + '/probe/register',
                          data={'mac': state['mac']},
                          timeout=TIMEOUT)
    else:
        return

    if r.status_code == 200:
        j = json.loads(r.content)
        # If the token we sent is activated
        if 'token' in j and j['token'] == state['token']:
            # Everything works
            store_token(state['token'])
            state['authenticated'] = True
            print("MobileAtlas Authenticated")
        # If the token we sent is still a token_candidate (not activated)
        elif 'token_candidate' in j and j['token_candidate'] == state['token']:
            state['authenticated'] = False
        # If we got a new token_candidate we use it the next time (but don't store it)
        elif 'token_candidate' in j:
            state['token'] = j['token_candidate']
            state['authenticated'] = False


def request_system_information(force=False):
    """
    Post the probe_system_information
    """
    too_old = state['last_system_information'] < datetime.utcnow() - timedelta(seconds=SYSTEM_INFO_UPDATE_INTERVAL)
    if force or not state['last_system_information'] or too_old:
        requests.post(MAM_URL + '/probe/system_information',
                      headers=token_header(),
                      json=get_system_information(),
                      timeout=TIMEOUT)
        state['last_system_information'] = datetime.utcnow()


def handle_command(command):
    if command == "exit":
        # Shutdown the Service with error code - systemd will restart it
        print("Stop Service because of Exit Command")
        sys.exit(1)
    elif command == "system_information":
        # Upload current system_information
        request_system_information(force=True)
    elif command == "git_pull":
        # Execute a git pull
        subprocess.check_output(["git", "-C", GIT_DIR, "pull"])
    else:
        print(f"Got unrecognized command {command}")


def main():
    # Service Startup
    requests.post(MAM_URL+'/probe/startup',
                  data={'mac': state['mac']},
                  timeout=TIMEOUT)

    while not state['authenticated']:
        authenticate()

        # Wait 60 seconds before next check
        if not state['authenticated']:
            print(f"Not Authenticated; Wait {RETRY_INTERVAL}")
            time.sleep(RETRY_INTERVAL)

    while True:
        request_system_information()

        # Main Polling Request
        r = requests.post(MAM_URL + '/probe/poll',
                          headers=token_header(),
                          timeout=TIMEOUT)

        # TODO better exception handling
        #   timeout, 403 cause unauthenticated, ...

        if r.status_code == 200 and r.content and r.json():
            print(f"Received {r.json()}")
            handle_command(r.json()['command'])


state = {"token": load_token(),
         "last_system_information": datetime.min,
         "authenticated": False,
         "mac": get_mac_addr()}

if __name__ == '__main__':
    print('MobileAtlas service startup')
    while 1:
        try:
            main()
        except Exception as e:
            print(f"MobileAtlas Exception {e}; Wait {RETRY_INTERVAL} before retry")
            time.sleep(RETRY_INTERVAL)
