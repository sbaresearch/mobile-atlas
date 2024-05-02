#!/usr/bin/env python3
# -*- Mode: python; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*-
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright (C) 2020 Aleksander Morgado <aleksander@aleksander.es>
#

import os, sys, signal, gi
from queue import Queue
from pathlib import Path

gi.require_version('Qmi', '1.0')
from gi.repository import GLib, Gio, Qmi
#https://www.freedesktop.org/software/libqmi/libqmi-glib/latest/
#https://lazka.github.io/pgi-docs/Qmi-1.0/mapping.html



def device_close_ready(qmidev,result,user_data=None):
    try:
        qmidev.close_finish(result)
    except GLib.GError as error:
        sys.stderr.write("Couldn't close QMI device: %s\n" % error.message)

def device_close(qmidev):
    qmidev.close_async(10, None, device_close_ready, None)

def release_client_ready(qmidev,result,user_data=None):
    try:
        qmidev.release_client_finish(result)
    except GLib.GError as error:
        sys.stderr.write("Couldn't release QMI client: %s\n" % error.message)
    device_close(qmidev)


def release_client(qmidev,qmiclient):
    qmidev.release_client(qmiclient, Qmi.DeviceReleaseClientFlags.RELEASE_CID, 10, None, release_client_ready, None)


def get_ids_ready(qmiclient,result,qmidev):
    try:
        output = qmiclient.get_ids_finish(result)
        output.get_result()
    except GLib.GError as error:
        sys.stderr.write("Couldn't query device ids: %s\n" % error.message)
        release_client(qmidev, qmiclient)
        return

    try:
        imei = output.get_imei()
        print("imei:                  %s" % imei)
    except:
        pass

    try:
        imei_software_version = output.get_imei_software_version()
        print("imei software version: %s" % imei_software_version)
    except:
        pass

    try:
        meid = output.get_meid()
        print("meid:                  %s" % meid)
    except:
        pass

    try:
        esn = output.get_esn()
        print("esn:                   %s" % esn)
    except:
        pass

    release_client(qmidev, qmiclient)


def get_capabilities_ready(qmiclient,result,qmidev):
    try:
        output = qmiclient.get_capabilities_finish(result)
        output.get_result()

        maxtxrate, maxrxrate, dataservicecaps, simcaps, radioifaces = output.get_info()
        print("max tx channel rate:   %u" % maxtxrate)
        print("max rx channel rate:   %u" % maxrxrate)
        print("data service:          %s" % Qmi.DmsDataServiceCapability.get_string(dataservicecaps))
        print("sim:                   %s" % Qmi.DmsSimCapability.get_string(simcaps))
        networks = ""
        for radioiface in radioifaces:
            if networks != "":
                networks += ", "
            networks += Qmi.DmsRadioInterface.get_string(radioiface)
        print("networks:              %s" % networks)

    except GLib.GError as error:
        sys.stderr.write("Couldn't query device capabilities: %s\n" % error.message)

    qmiclient.get_ids(None, 10, None, get_ids_ready, qmidev)



def create_device(device_path):
    def new_ready(unused, result, user_data=None):
        try:
            qmi_device = Qmi.Device.new_finish(result)
            user_data.put(qmi_device)
        except GLib.GError as error:
            sys.stderr.write("Couldn't create QMI device: %s\n" % error.message)
            return

    def open_ready(qmidev,result, user_data=None):
        try:
            device_is_open = qmidev.open_finish(result)
            user_data.put(device_is_open)
        except GLib.GError as error:
            sys.stderr.write("Couldn't open QMI device: %s\n" % error.message)
            return

    # get device path
    device_path = Gio.File.new_for_path(device_path)
    
    # get device
    result_queue = Queue()
    Qmi.Device.new(device_path, None, new_ready, result_queue)
    qmi_device = result_queue.get(timeout=10)
    
    # open device proxy
    result_queue = Queue()
    qmi_device.open(Qmi.DeviceOpenFlags.PROXY | Qmi.DeviceOpenFlags.AUTO, 10, None, open_ready, result_queue)
    device_is_open = result_queue.get(timeout=10)
    if device_is_open:
        return qmi_device
    print("error opening qmi device")
    return None


def allocate_client(qmi_device, service: Qmi.Service): #Qmi.Service.DMS
    def allocate_client_ready(qmidev, result, user_data=None):
        try:
            qmi_client = qmidev.allocate_client_finish(result)
            user_data.put(qmi_client)
        except GLib.GError as error:
            sys.stderr.write("Couldn't allocate QMI client: %s\n" % error.message)
            #device_close(qmidev)
            return
    result_queue = Queue()
    qmi_device.allocate_client(service, Qmi.CID_NONE, 10, None, allocate_client_ready, result_queue)
    qmi_client = result_queue.get(timeout=10)
    return qmi_client

# === Device Management Service (DMS) ===
def get_capabilities(device_path):
    def get_capabilities_ready(qmiclient, result, user_data=None):
        try:
            output = qmiclient.get_capabilities_finish(result)
            assert output.get_result() # returns True if the QMI operation succeeded, False if error is set

            maxtxrate, maxrxrate, dataservicecaps, simcaps, radioifaces = output.get_info()
            print("max tx channel rate:   %u" % maxtxrate)
            print("max rx channel rate:   %u" % maxrxrate)
            print("data service:          %s" % Qmi.DmsDataServiceCapability.get_string(dataservicecaps))
            print("sim:                   %s" % Qmi.DmsSimCapability.get_string(simcaps))
            networks = ""
            for radioiface in radioifaces:
                if networks != "":
                    networks += ", "
                networks += Qmi.DmsRadioInterface.get_string(radioiface)
            print("networks:              %s" % networks)

        except GLib.GError as error:
            sys.stderr.write("Couldn't query device capabilities: %s\n" % error.message)

    def get_ids_ready(qmiclient, result, user_data=None):
        try:
            output = qmiclient.get_ids_finish(result)
            output.get_result()
        except GLib.GError as error:
            sys.stderr.write("Couldn't query device ids: %s\n" % error.message)
            return

        try:
            imei = output.get_imei()
            print("imei:                  %s" % imei)
        except:
            pass
        try:
            imei_software_version = output.get_imei_software_version()
            print("imei software version: %s" % imei_software_version)
        except:
            pass
        try:
            meid = output.get_meid()
            print("meid:                  %s" % meid)
        except:
            pass
        try:
            esn = output.get_esn()
            print("esn:                   %s" % esn)
        except:
            pass

    qmi_device = create_device(device_path)
    qmi_client = allocate_client(qmi_device, Qmi.Service.DMS)
    qmi_client.get_capabilities(None, 10, None, get_capabilities_ready, None)
    qmi_client.get_ids(None, 10, None, get_ids_ready, None)
    release_client(qmi_device, qmi_client)




# === Persistent Device Configuration (PDC) ===
def mbn_id_str_to_int(mbn_id_str):
    mbn_id_int = [int(x,16) for x in mbn_id_str.split(':')]
    return mbn_id_int

def mbn_id_int_to_str(mbn_id_int):
    mbn_id_str = ''.join(f'{x:02X}:' for x in mbn_id_int).rstrip(':')
    return mbn_id_str

def set_selected_config(device_path, config_id_str, config_type=Qmi.PdcConfigurationType.SOFTWARE):
    def set_selected_config_ready(qmiclient, result, user_data=None):
        pass

    config_id_int = mbn_id_str_to_int(config_id_str)
    qmi_device = create_device(device_path)
    qmi_client = allocate_client(qmi_device, Qmi.Service.PDC)
    query_input = Qmi.MessagePdcSetSelectedConfigInput.new()
    query_input.set_type_with_id_v2(config_type, config_id_int)
    qmi_client.set_selected_config(query_input, 10, None, set_selected_config_ready, None)
    return

def delete_config(device_path, config_id_str, config_type=Qmi.PdcConfigurationType.SOFTWARE):
    # precondition: config_id must not be selected/active
    def delete_config_ready(qmiclient, result, user_data=None):
        pass

    config_id_int = mbn_id_str_to_int(config_id_str)
    qmi_device = create_device(device_path)
    qmi_client = allocate_client(qmi_device, Qmi.Service.PDC)
    query_input = Qmi.MessagePdcDeleteConfigInput.new()
    query_input.set_config_type(config_type)
    query_input.set_id(config_id_int)
    qmi_client.delete_config(query_input, 10, None, delete_config_ready, None)
    return





def list_mbn_configs(device_path):
    def list_configs_ready(qmiclient, result, user_data=None):
        # returns https://lazka.github.io/pgi-docs/Qmi-1.0/classes/MessagePdcListConfigsOutput.html#Qmi.MessagePdcListConfigsOutput
        # PROBLEM: MessagePdcListConfigsOutput does not contain any config info <.<
        # solution: get config list  via signal
        #try:
        #    output = qmiclient.list_configs_finish(result)
        #    #assert output.get_result() # returns True if the QMI operation succeeded, False if error is set
        #    print(output.get_result())
        #    user_data.put(output)
        #except GLib.GError as error:
        #    sys.stderr.write("Couldn't query pdc config: %s\n" % error.message)
        #    return
        print("list_configs_ready")
        pass

    def list_configs_signal(client_pdc, output, user_data=None):
        print("list_configs_signal")
        user_data.put(output.get_configs()) # besides get_configs there is also get_indication_result
    result_queue = Queue()
    qmi_device = create_device(device_path)
    qmi_client = allocate_client(qmi_device, Qmi.Service.PDC)

    object_added_id = qmi_client.connect('list-configs', list_configs_signal, result_queue)
    query_input = Qmi.MessagePdcListConfigsInput.new()
    query_input.set_config_type(Qmi.PdcConfigurationType.SOFTWARE)
    print(query_input)

    qmi_client.list_configs(query_input, 10, None, list_configs_ready, result_queue)
    config_list = result_queue.get(timeout=10)

    
    def get_selected_config_ready(qmiclient, result, user_data=None):
        pass
    def get_selected_config_signal(client_pdc, output, user_data=None):
        try:
            user_data.put(output.get_active_id())
        except GLib.GError as error:
            user_data.put(None)
        try:
            user_data.put(output.get_pending_id())
        except GLib.GError as error:
            user_data.put(None)

    result_queue = Queue()
    object_added_id = qmi_client.connect('get-selected-config', get_selected_config_signal, result_queue)
    
    query_input = Qmi.MessagePdcGetSelectedConfigInput.new()
    query_input.set_config_type(Qmi.PdcConfigurationType.SOFTWARE)
    qmi_client.get_selected_config(query_input, 10, None, get_selected_config_ready, result_queue)
    active_id = result_queue.get(timeout=10)
    pending_id = result_queue.get(timeout=10)

    def get_config_info_ready(qmiclient, result, user_data=None):
        print("get_config_info_ready")

    def get_config_info_ready_signal(client_pdc, output, user_data=None):
        print("get_config_info_ready_signal")
        config = {
            "Description": output.get_description(),
            "Type": None,
            "Size": output.get_total_size(),
            "Status": "Inactive",
            "Version": output.get_version(),
            "ID": None
        }
        user_data.put(config)

    result_queue = Queue()
    object_added_id = qmi_client.connect('get-config-info', get_config_info_ready_signal, result_queue)

    ret = []
    for c in config_list:
        #print(f"{c.config_type}: {c.id}")
        id_bytes = bytes(c.id)
        query_input = Qmi.MessagePdcGetConfigInfoInput.new()
        query_input.set_type_with_id_v2(c.config_type, c.id)
        qmi_client.get_config_info(query_input, 10, None, get_config_info_ready, result_queue)
        config = result_queue.get(timeout=10)
        config["Type"] = c.config_type
        config["ID"] = mbn_id_int_to_str(c.id)
        if id_bytes == active_id:
            config["Status"] = "Active"
        elif id_bytes == pending_id:
            config["Status"] = "Pending"
        ret.append(config)
    if ret:
        return ret
    print("error getting config")
    return None

# load new mbn file into modem config
def load_mbn_file(device_path, mbn_path):
    if not Path(mbn_path).exists():
        return
    
    # hotfix because libqmi does not support easy loading mbns via file path (but requires complex chunk object :-/)
    os.system(f"qmicli --device={device_path} --device-open-proxy --pdc-load-config='{mbn_path}'")
    return
    #qmi_device = create_device(device_path)
    #qmi_client = allocate_client(qmi_device, Qmi.Service.PDC)
    ## not sure if needed
    #mbn_path = Gio.File.new_for_path(mbn_path)
    ## TODO load chunks?
    ## https://gitlab.freedesktop.org/mobile-broadband/libqmi/-/blob/main/src/qmicli/qmicli-pdc.c?ref_type=heads#L1266
    ## https://lazka.github.io/pgi-docs/Qmi-1.0/classes/MessagePdcLoadConfigInput.html
    #qmi_client.load_config(TODO, 30, None, activate_config_finish, None)
    #release_client(qmi_device, qmi_client)



