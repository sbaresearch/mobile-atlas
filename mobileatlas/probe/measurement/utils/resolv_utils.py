#https://stackoverflow.com/a/63185592
# mock /etc/hosts
# lock it in multithreading or use multiprocessing if an endpoint is bound to multiple IPs frequently
import socket

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


def _get_ip(domain_name):
    try:
        data = socket.gethostbyname(domain_name)
        ip = data
        return ip
    except Exception:
        return None

def _bind_ip(domain_name, port, ip):
    '''
    resolve (domain_name,port) to a given ip
    '''
    key = (domain_name, port)
    # (family, type, proto, canonname, sockaddr)
    value = (socket.AddressFamily.AF_INET, socket.SocketKind.SOCK_STREAM, 6, '', (ip, port))
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