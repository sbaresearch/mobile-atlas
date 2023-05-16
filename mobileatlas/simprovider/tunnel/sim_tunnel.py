import socket
import threading
import logging
from pySim.transport import LinkBase
from pySim.utils import b2h, h2b

class SimTunnel(threading.Thread):
    """
    Connect a SimLink with a TCP Connection
    """
    def __init__(self, connection, sl, iccid, do_pbs=True):
        self.connection = connection
        self.sl = sl
        self.iccid = iccid
        self.probe_endpoint = connection.getpeername()[0]
        self.do_pbs = do_pbs
        self.connected = False
        threading.Thread.__init__(self)

    def run(self):
        self.sl.connect()
        self.connected = True
        self.maintain_connection()

    def maintain_connection(self):
        """
        Loop to receive data for local SIM
        """
        try:
            while self.connected:
                self.process_packet()
        except Exception as e:
            logging.fatal(e, exc_info=True)
        finally:
            # Clean up the connection
            # logging.info("serial buffer: " + str(bin2hex(self.sl.rx_bytes())))
            # self.sl.disconnect()
            logging.info("close connection")
            self.sl.disconnect()
            self.connection.close()

    def process_packet(self, retries = 5):
        """
        Retrieve and process packets
        """
        # receive 5 header bytes (cla, ins, p1, p2, p3)
        apdu = self.connection.recv()

        if apdu == None:
            self.connected = False
            logging.info("peer closed connection")
            return

        logging.info(f"received apdu[{len(apdu.payload)}]: {b2h(apdu.payload)}")
        data, sw = self.sl.send_apdu(b2h(apdu.payload))
        resp = h2b(data + sw)
        self.connection.send_apdu(resp) # TODO
        logging.info(f"sent data: {resp}")
