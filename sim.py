#!/usr/bin/env python3
"""
SIM Server Script
"""

import logging
import socket
import struct
import argparse
from mobileatlas.simprovider.sim_provider import SimProvider
from mobileatlas.simprovider.tunnel.sim_tunnel import SimTunnel


HOST_DEFAULT = "0.0.0.0"
PORT_DEFAULT = 8888


def init_server(host, port):
    """
    Create and return the TCP/IP Socket
    """
    # Create a TCP/IP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_address = (host, port)
    logging.info('starting up on {} port {}'.format(*server_address))
    s.bind(server_address)

    # Listen for incoming connections
    s.listen(1)
    return s


def accept_connection(s):
    """
    Wait for a connection, accept it, and return it
    """
    # Wait for a connection
    logging.info('waiting for a connection')
    connection, client_address = s.accept()
    logging.info('accept connection ' + str(client_address))
    return connection


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(conflict_handler="resolve")
    parser.add_argument('-h', '--host', default=HOST_DEFAULT, help="IP for TCP/IP Socket")
    parser.add_argument('-p', '--port', type=int, default=PORT_DEFAULT, help="Port for TCP/IP Socket")
    args = parser.parse_args()

    # sim_mapping[ imsi:string ] = serial_port:string
    sim_provider = SimProvider()
    available_sims = sim_provider.get_sims()


    srv = init_server(args.host, args.port)

    while True:
        connection = accept_connection(srv)

        # First 8 Byte is the IMSI
        requested_imsi = struct.unpack('!Q', connection.recv(8))[0]

        device = next((x for x in available_sims if x.imsi == str(requested_imsi)), None)
        if device:
            logging.info(f"requested imsi {requested_imsi} is on device {device.device_name}")
            # Start SimTunnel for connection to serial device
            #tunnel = SimTunnel(connection, SerialSimLink(device))
            #tunnel = SimTunnel(connection, BluetoothSapSimLink("80:5A:04:0E:90:F6"))
            #tunnel = SimTunnel(connection, ModemATCommandLink("/dev/ttyACM0"))
            tunnel = SimTunnel(connection, device.sl)
            tunnel.start()
            # tunnel.join()
        else:
            logging.info(f"requested imsi {requested_imsi} is currently not connected to the system")
            connection.close()

if __name__ == "__main__":
    main()
