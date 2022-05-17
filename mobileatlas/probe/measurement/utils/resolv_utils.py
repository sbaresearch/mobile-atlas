#https://stackoverflow.com/a/63185592
# mock /etc/hosts
# lock it in multithreading or use multiprocessing if an endpoint is bound to multiple IPs frequently
import socket
import ipaddress

etc_hosts = {}
# decorate python built-in resolver
def custom_resolver(builtin_resolver):
    def wrapper(*args, **kwargs):
        try:
            return etc_hosts[args[:2]]
        except KeyError:
            # fall back to builtin_resolver for endpoints not in etc_hosts
            return builtin_resolver(*args, **kwargs)

    return wrapper

# monkey patching
socket.getaddrinfo = custom_resolver(socket.getaddrinfo)

#https://stackoverflow.com/questions/16276913/reliably-get-ipv6-address-in-python
def _get_ips(domain_name, port=None, ip='ipv4v6'):
    try:
        # search for all addresses, but take only the v6 ones
        alladdr = socket.getaddrinfo(domain_name, port)
        ip4 = filter(
            lambda x: x[0] == socket.AF_INET,
            alladdr
        )
        ip6 = filter(
            lambda x: x[0] == socket.AF_INET6, # means its ip6
            alladdr
        )
        if ip == 'ipv4':
            return list(set([a[0] for a in [e[4] for e in ip6]]))
        elif ip == 'ipv6':
            return list(set([a[0] for a in [e[4] for e in ip6]]))
        else:
            return list(set([a[0] for a in [e[4] for e in alladdr]]))
    except Exception:
        return []

def _bind_ips(domain_name, port, ips):
    '''
    resolve (domain_name,port) to a given ip
    '''
    key = (domain_name, port)
    value_v4 = []
    value_v6 = []
    for ip in ips:
        ipaddr = ipaddress.ip_address(ip)
        # (family, type, proto, canonname, sockaddr)
        if ipaddr.version == 4:
            value_v4.append((socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_STREAM, 6, '', (ip, port)))
            value_v4.append((socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_DGRAM, 17, '', (ip, port)))
            value_v4.append((socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_RAW, 0, '', (ip, port)))
        else:
            value_v6.append((socket.AddressFamily.AF_INET6, socket.SocketKind.SOCK_STREAM, 6, '', (ip, port, 0, 0)))
            value_v6.append((socket.AddressFamily.AF_INET6, socket.SocketKind.SOCK_DGRAM, 17, '', (ip, port, 0, 0)))
            value_v6.append((socket.AddressFamily.AF_INET6, socket.SocketKind.SOCK_RAW, 0, '', (ip, port, 0, 0)))
    value = [*value_v6, *value_v4] #prefer ipv6 over ipv4
    if value:
        etc_hosts[key] = value

def _remove_binding(domain_name, port):
    try:
        del etc_hosts[(domain_name, port)]
        return True
    except KeyError:
        return False

def _fix_ip(domain_name, port):
    ips = _get_ips(domain_name)
    _bind_ips(domain_name, port, ips)
    return bool(ips)