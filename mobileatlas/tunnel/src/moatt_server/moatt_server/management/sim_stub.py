import requests
import json
from datetime import datetime
import logging
import time
import sys

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(message)s")

SERVER = "http://localhost:5000"
API_POLL = "/sim/poll"
API_REGISTER = "/sim/register"
HEADERS = {"Authorization": "Bearer U1CWK1iZrjBRKMFvAt6UAYK6rzyAXD4q"}


def main():
    while 1:

        try:
            logging.info("Start polling")

            r = requests.post(SERVER + API_POLL, headers=HEADERS)
            logging.info(f"{r.url}")
            if r.status_code != 200:
                logging.error(r)
                time.sleep(5)
            else:
                logging.info(r.content)
        except requests.exceptions.ConnectionError:
            logging.error("Connection error - wait")
            time.sleep(5)


if __name__ == '__main__':
    main()
