import socket
import threading
import logging
from pySim.transport import LinkBase
from pySim.utils import b2h, h2b

class SimTunnel(threading.Thread):
    """
    Connect a SimLink with a TCP Connection
    """
    def __init__(self, connection, sl, iccid, do_pbs=True, direct_connection=False):
        self.connection = connection
        self.sl = sl
        self.iccid = iccid
        self.probe_endpoint = connection.getpeername()[0]
        self.do_pbs = do_pbs
        self.connected = False
        self.direct_connection = direct_connection
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
            try:
                self.connection.unwrap()
            except:
                pass
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

    def process_packet_indirect(self):
        apdu = self.connection.recv()

        if apdu == None:
            self.connected = False
            logging.info("peer closed connection")
            return

        logging.info(f"received apdu[{len(apdu.payload)}]: {b2h(apdu.payload)}")
        data, sw = self.sl.send_apdu(b2h(apdu.payload))
        resp = h2b(data + sw)
        self.connection.send_apdu(resp) # TODO: handle apdu ops
        logging.info(f"sent data: {resp}")

    def process_packet_direct(self):
        # receive 5 header bytes (cla, ins, p1, p2, p3)
        apdu = self.connection.recv(256)

        if(len(apdu) < 5):
            self.connected = False
            logging.info("not enough bytes received -> disconnect")
            return

        logging.info(f"received apdu[{len(apdu)}]: {b2h(apdu)}")
        data, sw = self.sl.send_apdu(b2h(apdu))

        resp = h2b(data + sw)
        self.connection.send(resp)
        logging.info(f"sent data: {resp}")

    def process_packet(self):
        """
        Retrieve and process packets
        """

        if self.direct_connection:
            self.process_packet_direct()
        else:
            self.process_packet_indirect()
