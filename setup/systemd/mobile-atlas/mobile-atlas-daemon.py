#!/usr/bin/python3
import json
import os
import sys
import time
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

#hack to add probe utlities module
PROBE_UTILITIES_DIR = "/home/pi/mobile-atlas/setup/systemd/"
sys.path.append(PROBE_UTILITIES_DIR)
import probe_utilities

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
            probe_utilities.store_token(TOKEN_STORAGE_DIR, state['token'])
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
                      json=probe_utilities.get_system_information(),
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
    probe_utilities.write_activity_log("0", "ServiceStartup", datetime.utcnow().isoformat(timespec='seconds'))
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


state = {"token": probe_utilities.load_token(TOKEN_STORAGE_DIR),
         "last_system_information": datetime.min,
         "authenticated": False,
         "mac": probe_utilities.get_mac_addr()}

if __name__ == '__main__':
    print('MobileAtlas service startup')
    while 1:
        try:
            main()
        except Exception as e:
            print(f"MobileAtlas Exception {e}; Wait {RETRY_INTERVAL} before retry")
            time.sleep(RETRY_INTERVAL)
