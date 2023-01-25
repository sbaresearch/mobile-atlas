import logging

from server.auth import read_tokens

from tunnelTypes.connect import Imsi
from clients.probe_client import ProbeClient

logger = logging.getLogger(__name__)
token = read_tokens()[0]

def main():
    logging.basicConfig(level=logging.DEBUG)
    c = ProbeClient(2, token, "::1", 5555)
    #stream = c.connect(Imsi(b"\x01\x02\x03\x04\x05\x06\x07\x08"))
    stream = c.connect(Imsi("12345678"))

    if stream == None:
        raise Exception("Connection failed.")

    logger.debug("Successfully received a connection.")

    for i in range(10):
        stream.send_apdu(f"s{i}".encode())
        logger.debug("Sent message.")

        apdu = stream.recv()

        if apdu == None:
            logger.error("Error receiving apdu.")
            return

        print(f"Received APDU: {apdu.payload}")

    apdu = stream.recv()
    print(f"Received: {apdu}")


if __name__ == "__main__":
    main()
