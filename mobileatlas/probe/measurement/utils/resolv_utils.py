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
def _get_ip(domain_name, port=None, ip='ipv4v6'):
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
        if ip is 'ipv4':
            return list(ip4)[0][4][0]
        elif ip is 'ipv6':
            return list(ip6)[0][4][0]
        else:
            return alladdr[0][4][0]
    except Exception:
        return None

def _bind_ip(domain_name, port, ip):
    '''
    resolve (domain_name,port) to a given ip
    '''
    key = (domain_name, port)
    ipaddr = ipaddress.ip_address(ip)
    # (family, type, proto, canonname, sockaddr)
    if ipaddr.version == 4:
        value = (socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_STREAM, 6, '', (ip, port))
    else:
        value = (socket.AddressFamily.AF_INET6, socket.SocketKind.SOCK_STREAM, 6, '', (ip, port, 0, 0))
        
    etc_hosts[key] = [value]

def _remove_binding(domain_name, port):
    try:
        del etc_hosts[(domain_name, port)]
        return True
    except KeyError:
        return False

def _fix_ip(domain_name, port):
    ip = _get_ip(domain_name)
    if ip is not None:
        _bind_ip(domain_name, port, ip)
        return True
    return False