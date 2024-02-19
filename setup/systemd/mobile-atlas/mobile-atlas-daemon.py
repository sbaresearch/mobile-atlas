#!/usr/bin/python3

import sys
import time
import requests
import subprocess
from datetime import datetime, timedelta, timezone

# TODO: specify dependency
#hack to add probe utlities module
#PROBE_UTILITIES = "/usr/local/lib/mobile-atlas/"
PROBE_UTILITIES = "/home/pf/Documents/mobile-atlas-merge/setup/systemd/"
sys.path.append(PROBE_UTILITIES)
import probe_utilities as probe_util
from probe_utilities import now

#MAM_URL = "https://mam.mobileatlas.eu"
MAM_URL = "http://localhost:5000"
NET_INTERFACE = "eth0"
TOKEN_STORAGE_DIR = "/etc/mobileatlas/"
GIT_DIR = "/home/pi/mobile-atlas/"
# Todo improve test/prod config

# Seconds to wait for after Exception
RETRY_INTERVAL = 10
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

def authenticate(token):
    if not state['registered']:
        resp = probe_util.register_token(token, mac=state['mac'])

        if not resp.ok:
            return

    state['registered'] = True

    if not probe_util.is_token_active(token):
        return
    else:
        state['authenticated'] = True

def request_system_information(force=False):
    """
    Post the probe_system_information
    """
    too_old = state['last_system_information'] < now() - timedelta(seconds=SYSTEM_INFO_UPDATE_INTERVAL)
    if force or not state['last_system_information'] or too_old:
        requests.post(MAM_URL + '/probe/system_information',
                      headers=token_header(),
                      json=probe_util.get_system_information(),
                      timeout=TIMEOUT)
        state['last_system_information'] = now()


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

def auth_loop():
    token = state['token']
    while not state['authenticated']:
        authenticate(token)

        # Wait 60 seconds before next check
        if not state['authenticated']:
            print(f"Not Authenticated; Wait {RETRY_INTERVAL}")
            time.sleep(RETRY_INTERVAL)

def main():
    # Service Startup
    probe_util.write_activity_log("0", "ServiceStartup", now().isoformat(timespec='seconds'))

    auth_loop()

    requests.post(MAM_URL+'/probe/startup',
                  data={'mac': state['mac']},
                  headers=token_header(),
                  timeout=TIMEOUT)

    min_inter_poll_time = timedelta(seconds=RETRY_INTERVAL / 2)
    while True:
        request_system_information()

        # Main Polling Request
        poll_start = now()
        r = requests.post(MAM_URL + '/probe/poll',
                          headers=token_header(),
                          timeout=TIMEOUT)
        poll_duration = now() - poll_start

        # TODO better exception handling
        #   timeout, 403 cause unauthenticated, ...

        if r.status_code == 200 and r.content and r.json():
            print(f"Received {r.json()}")
            handle_command(r.json()['command'])

        # TODO: find meaningful retry value
        if poll_duration < min_inter_poll_time:
            time.sleep((min_inter_poll_time - poll_duration).total_seconds())

state = {"token": probe_util.load_or_create_token(TOKEN_STORAGE_DIR),
         "registered": False,
         "last_system_information": datetime.min.replace(tzinfo=timezone.utc),
         "authenticated": False,
         "mac": probe_util.get_mac_addr(NET_INTERFACE)}

if __name__ == '__main__':
    print('MobileAtlas service startup')
    while 1:
        try:
            main()
        except Exception as e:
            print(f"MobileAtlas Exception {e}; Wait {RETRY_INTERVAL} before retry")
            time.sleep(RETRY_INTERVAL)
