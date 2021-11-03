import boto3
import time
import logging
from urllib.parse import urlparse

import socket
from contextlib import closing

logger = logging.getLogger(__name__)

def is_port_open(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        if sock.connect_ex((host, port)) == 0:
            #print("port open")
            return True
        else:
            #print("port closed")
            return False


class Ec2Instance():
    SCRIPT_HEADER = '''#!/bin/bash
    yum -y install socat;
    '''

    def __init__(self, id, key, region='eu-central-1'):
        self.ec2 = boto3.resource(
            'ec2',
            aws_access_key_id=id,
            aws_secret_access_key=key,
            region_name=region
        )
        self.instance = None
    
    def start_instance_startup_script(self, startup_script):
        instance = self.ec2.create_instances(
            ImageId='ami-0453cb7b5f2b7fca2',
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.micro',
            SecurityGroups=['MobileAtlasAllPorts'],
            UserData=startup_script,
        )
        self.instance = instance[0]
        logger.info(f"wait until instance {self.instance.id} is up and running")
        self.instance.wait_until_running()
        self.instance.reload() #refresh info, to get public ip addr
        logger.info(f"instance running, ip address is {self.instance.public_ip_address}")

    def start_instance_port_forward(self, port_forwards):
        startup_script = Ec2Instance.SCRIPT_HEADER
        for p in port_forwards:
            startup_script += Ec2Instance.get_portforward_command(p.get('src_port'), p.get('target_host'), p.get('target_port'))
        self.start_instance_startup_script(startup_script)

    def wait_for_portforward(self, port):
        ip = self.get_ip()
        while(not is_port_open(ip, port)):
            time.sleep(1)

    def start_instance_web_forward(self, url):
        domain = urlparse(url).hostname #netloc
        port_forwards = [
            {'src_port':80, 'target_host':domain},
            {'src_port':443, 'target_host':domain}
        ]
        self.start_instance_port_forward(port_forwards)
        self.wait_for_portforward(port=80)

    def stop_instance(self):
        logger.info("stopping ec2 instance")
        self.instance.terminate()
        self.instance.wait_until_terminated()

    def get_ip(self):
        if self.instance:
            return self.instance.public_ip_address
        return None

    @staticmethod
    def get_portforward_command(src_port, target_host, target_port = None):
        if not target_port:
            target_port = src_port
        script_portforward = f'''
        socat tcp-listen:{src_port},reuseaddr,fork tcp-connect:{target_host}:{target_port} &
        socat udp-listen:{src_port},reuseaddr,fork udp:{target_host}:{target_port} &
        '''
        return script_portforward






