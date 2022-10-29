from flask import Flask
from flask import render_template
from datetime import datetime, timedelta
import humanize

#hack to add probe utlities module
import sys
from pathlib import Path
PROBE_UTILITIES_DIR = str(Path(__file__).parent.parent.resolve())
print(PROBE_UTILITIES_DIR)
sys.path.append(PROBE_UTILITIES_DIR)
import probe_utilities


app = Flask(__name__, template_folder='template', static_folder='template/assets')

def format_network_interface(interface_list, interface_name="eth0"):
    iface = probe_utilities.filter_network_info(interface_list, interface_name)
    iface_ip = probe_utilities.extract_ip_addr(iface)
    iface_rx_bytes, iface_tx_bytes = probe_utilities.extract_traffic_stats(iface)
    iface_stats = None
    if iface_rx_bytes and iface_tx_bytes:
        iface_stats = f"{humanize.naturalsize(iface_rx_bytes)} (RX), {humanize.naturalsize(iface_tx_bytes)} (TX)"
    return iface_ip, iface_stats
        

@app.route("/")
def hello_world():
    # system
    uptime_seconds = probe_utilities.get_uptime()
    uptime = None
    if uptime_seconds:
        uptime = timedelta(seconds=int(uptime_seconds))
    temp = probe_utilities.get_temperature()
    temperature = None
    if temp:
        temperature = f"{round(temp, 1)} °C"
    
    system = {
        'uptime' : uptime,
        'temperature' : temperature
    }
    
    # network
    mac = probe_utilities.get_mac_addr().upper()
    hostname = probe_utilities.get_hostname()
    interface_list = probe_utilities.get_network_info()
    eth0_ip, eth0_stats = format_network_interface(interface_list, "eth0")
    wg0_ip, wg0_stats = format_network_interface(interface_list, "wg0")
        
    network = {
        'mac_address' : mac,
        'hostname' : hostname,
        'interfaces' :{
            'Ethernet' : {
                'ip_address' : eth0_ip,
                'traffic_stats' : eth0_stats
            },
            'Wireguard' : {
                'ip_address' : wg0_ip,
                'traffic_stats' : wg0_stats
            }
        }
    }
    
    # activity
    max_activity_count = 5
    activities = probe_utilities.get_activities()
    service_activities = probe_utilities.filter_activities(activities, 'ServiceStartup')
    [x.update({'id':idx}) for idx, x in enumerate(service_activities)]
    service_activities.reverse()
    
    measurement_activities = probe_utilities.filter_activities(activities, 'Test')
    [x.update({'id':idx}) for idx, x in enumerate(measurement_activities)]
    measurement_activities.reverse()
    
    activities = {
        'service' : service_activities[:max_activity_count],
        'measurement' : measurement_activities[:max_activity_count],
        'measurement_cnt' : len(measurement_activities)
    }
    return render_template('index.html', system_info=system, network_info=network, activities=activities)
