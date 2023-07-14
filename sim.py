#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

"""
SIM Server Script
"""

import os
import sys
import ssl
import logging
import argparse
import base64
import time
from mobileatlas.simprovider.sim_provider import SimProvider
from mobileatlas.simprovider.tunnel.sim_tunnel import SimTunnel

from moatt_clients.provider_client import ProviderClient, register_sims
from moatt_clients.client import register, deregister, AuthError
from moatt_types.connect import Token, ConnectStatus, Imsi, Iccid

PORT_DEFAULT = 6666

def provides_sim(sim_provider, req):
    device = next((x for x in sim_provider.get_sims() if Imsi(x.imsi) == req.identifier or Iccid(x.iccid) == req.identifier), None)

    if device:
        return ConnectStatus.Success
    else:
        return ConnectStatus.NotFound

def get_sims(sim_provider):
    return [{"iccid": x.iccid, "imsi": x.imsi} for x in sim_provider.get_sims()]

def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(conflict_handler="resolve")
    parser.add_argument('-h', '--host', required=True, help="SIM server address")
    parser.add_argument('-p', '--port', type=int, default=PORT_DEFAULT, help="SIM server port")
    parser.add_argument('-b', '--bluetooth-mac', type=str, required=False,
                        help='MAC address of the bluetooth device (rSAP)')
    parser.add_argument('-a', '--api-url', required=True,
                        help="MobileAtlas-tunnel-server REST API URL")
    parser.add_argument('--cafile', help='CA certificates used to verify SIM server certificate. \
(File of concatenated certificates in PEM format.)')
    parser.add_argument('--capath', help='Path to find CA certificates used to verify SIM server \
certificate.')
    parser.add_argument('--tls-server-name', help='SIM server name used in certificate \
verification. (defaults to the value of --host)')
    args = parser.parse_args()

    env_token = os.environ.get("API_TOKEN")

    if env_token is None:
        logging.error("API_TOKEN environment variable is unset.")
        return

    try:
        token = Token(base64.b64decode(env_token))
    except:
        logging.error("API_TOKEN environment variable contains a malformed API token.")
        return

    sim_provider = SimProvider(args.bluetooth_mac)
    sims = get_sims(sim_provider)
    session_token = register(args.api_url, token)

    if session_token is None:
        logging.error("Registration failed.")
        return

    try:
        sim_provider.set_device_change_callback(lambda: register_sims(args.api_url, session_token, get_sims(sim_provider)))
        if register_sims(args.api_url, session_token, sims) is None:
            logging.error("SIM card registration failed.")
            return

        tls_ctx = ssl.create_default_context(cafile=args.cafile, capath=args.capath)

        if args.tls_server_name is None:
            server_hostname = args.host
        else:
            server_hostname = args.tls_server_name

        srv = ProviderClient(
                session_token,
                args.host,
                args.port,
                lambda x: provides_sim(sim_provider, x),
                tls_ctx=tls_ctx,
                server_hostname=server_hostname,
                )

        failed_connections = 0
        while True:
            id_connection = None
            try:
                id_connection = srv.wait_for_connection()
            except AuthError as e:
                logging.error(f"Authentication with SIM tunnel failed: {e}\nStopping...")
                return
            except Exception as e:
                logging.warn(f"Error while establishing connection: {e}")

            if id_connection is None:
                failed_connections += 1

                if failed_connections > 10:
                    logging.error("Multiple consecutive connection attempts failed. Stopping...")
                    return

                time.sleep(1)
                continue

            failed_connections = 0

            requested_sim = id_connection[0]
            connection = id_connection[1]

            device = next((x for x in sim_provider.get_sims() if Iccid(x.iccid) == requested_sim or Imsi(x.imsi) == requested_sim), None)
            if device:
                logging.info(f"requested imsi {requested_sim} is on device {device.device_name}")
                # Start SimTunnel for connection to serial device
                #tunnel = SimTunnel(connection, SerialSimLink(device))
                #tunnel = SimTunnel(connection, BluetoothSapSimLink("80:5A:04:0E:90:F6"))
                #tunnel = SimTunnel(connection, ModemATCommandLink("/dev/ttyACM0"))
                tunnel = SimTunnel(connection, device.sl, device.iccid)
                tunnel.start()
            else:
                logging.info(f"requested imsi {requested_sim} is currently not connected to the system")
                connection.close()
    finally:
        deregister(args.api_url, session_token)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as keyboard_interrupt:
        print('Interrupted')
        try:
            sys.exit(1)
        except SystemExit as system_exit:
            os._exit(system_exit.code)
