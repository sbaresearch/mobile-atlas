import logging

from server.auth import read_tokens

from tunnelTypes.connect import ConnectStatus
from clients.provider_client import ProviderClient

logger = logging.getLogger(__name__)
token = read_tokens()[0]

def main():
    logging.basicConfig(level=logging.DEBUG)
    c = ProviderClient(1, token, "::1", 6666, lambda _: ConnectStatus.Success)
    stream = c.wait_for_connection()

    if stream == None:
        raise Exception("Connection failed.")

    logger.debug("Successfully received a connection.")

    for i in range(10):
        apdu = stream.recv()

        if apdu == None:
            logger.error("Error receiving apdu.")
            return

        print(f"Received APDU: {apdu.payload}")

        stream.send_apdu(apdu.payload + f"s{i}".encode())

    apdu = stream.recv()
    print(f"Received: {apdu}")

if __name__ == "__main__":
    main()
