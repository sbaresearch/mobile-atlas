import boto3
import time
import logging
from urllib.parse import urlparse

import json
import socket
from contextlib import closing

logger = logging.getLogger(__name__)

def is_port_open(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(10)
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

    def __init__(self, id=None, key=None, region='eu-central-1'):
        if key is None:
            with open("/home/pi/mobile-atlas-config/test_config/ec2.json", "r") as jsonfile:
                #os.environ.get('EC2_ID') # does not work because env is isolated in namespace; maybe fix it by linking env file to ns?
                json_dict = json.load(jsonfile)
                id = json_dict.get('id')  
                key = json_dict.get('key')
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
            InstanceType='t2.nano',
            SecurityGroups=['MobileAtlasAllPorts'],
            UserData=startup_script,
        )
        self.instance = instance[0]
        logger.info(f"wait until instance {self.instance.id} is up and running")
        self.instance.wait_until_running()
        self.instance.reload() #refresh info, to get public ip addr
        logger.info(f"instance running, ip addresses are {*self.get_ip(),}")

    def start_instance_port_forward(self, port_forwards):
        startup_script = Ec2Instance.SCRIPT_HEADER
        for p in port_forwards:
            startup_script += Ec2Instance.get_portforward_command(p.get('src_port'), p.get('target_host'), p.get('target_port'))
        self.start_instance_startup_script(startup_script)

    def wait_for_portforward(self, port):
        ip = self.get_ip()[0]
        while(not is_port_open(ip, port)):
            time.sleep(1)
            
    def start_instance_forward(self, target_host, ports=[80, 443]):
        port_forwards = []
        for p in ports:
            port_forwards.append( {'src_port': p, 'target_host':target_host})
        self.start_instance_port_forward(port_forwards)
        self.wait_for_portforward(ports[0])

    def start_instance_forward_web(self, url):
        domain = urlparse(url).hostname #netloc
        self.start_instance_forward(domain, [80,443])
         
    def start_instance_forward_dns(self, dns_server):
        self.start_instance_forward(dns_server, [53])

    def stop_instance(self):
        logger.info("stopping ec2 instance")
        self.instance.terminate()
        self.instance.wait_until_terminated()

    def get_ip(self):
        if self.instance:
            return list(filter(lambda v: v is not None, [self.instance.public_ip_address, self.instance.ipv6_address]))
        return None

    @staticmethod
    def get_portforward_command(src_port, target_host, target_port = None):
        if not target_port:
            target_port = src_port
        script_portforward = f'''
        sysctl -w net.ipv6.bindv6only=1;
        socat tcp4-listen:{src_port},reuseaddr,fork tcp4-connect:{target_host}:{target_port} &
        socat udp4-listen:{src_port},reuseaddr,fork udp4:{target_host}:{target_port} &
        socat tcp6-listen:{src_port},reuseaddr,fork tcp6-connect:{target_host}:{target_port} &
        socat udp6-listen:{src_port},reuseaddr,fork udp6:{target_host}:{target_port} &
        '''
        return script_portforward






