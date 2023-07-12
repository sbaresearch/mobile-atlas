import requests

"""
This script updates the probes status to offline
It includes a Mattermost Webhook to notify when probes are offline for some time

crontab -e
* * * * * python3 ~/status_check_cron.py
"""

# TODO remove hardcoded 30 minutes in notification
# TODO decouple notification from status check

WEBHOOK_URL = ""
MAM_URL = "https://mam.mobileatlas.eu/probes/check_status"
AUTH_USER = "REDACTED"
AUTH_PSW = "REDACTED"

r = requests.get(MAM_URL, auth=(AUTH_USER, AUTH_PSW))
if r.status_code == 200 and r.json() and WEBHOOK_URL:
    for p in r.json():
        text = f"Probe {p['name']+' - '+p['mac'] if 'name' in p and p['name'] else p['mac']} is offline for 30 minutes"
        requests.post(WEBHOOK_URL, json={'text': text})
