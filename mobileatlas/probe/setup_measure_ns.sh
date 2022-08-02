#!/bin/bash
#
# This script starts NetworkManager and ModemManager
# Unshare divides the namespaces (mount, net, pid) from python parent
# Then mount tmpfs, and do some magic
# Then start the dbus daemon, cause NM and MM communicatore over DBus
# Finally, start NetworkManager, ModemManager and tcpdump

#namespace name
NSNAME_DEFAULT=ns_mobileatlas

NSNAME="${1:-$NSNAME_DEFAULT}"

ns_mobileatlas

#create mobileatlas tmp directory
mkdir -p /tmp/mobileatlas;
rm -rf /tmp/mobileatlas/*;

#create directory where netns are mapped in case it's not already present (note /run == /var/run)
mkdir -p /run/netns;

#create netns directory and make separate /etc/resolv.conf
mkdir -p /etc/netns/${NSNAME};
cp /dev/null /etc/netns/${NSNAME}/resolv.conf;

#create link to default NS to make it easily accessible within the measurement ns
ln -sf /proc/1/ns/net /run/netns/default;

#remove mount of previous test in case it wasn't successfully deleted
umount /run/netns/${NSNAME};

# use persistent mount for net namespace, path is compatible with ip netns etc.
# in case we'd want to use persistent mount namespaces we'd use private filesystem (see https://github.com/karelzak/util-linux/issues/289 or http://karelzak.blogspot.com/2015/04/persistent-namespaces.html)
touch /run/netns/${NSNAME};

#enable ip forwarding
sysctl -w net.ipv4.ip_forward=1

#create iptable rules for traffic forwarding
iptables -A INPUT \! -i veth1 -s 10.29.183.0/24 -j DROP;
iptables -t nat -A POSTROUTING -s 10.29.183.0/24 -o wg+ -j MASQUERADE;

#fix wwan0 interface
sudo ifconfig wwan0 down; sudo echo 'Y' | sudo tee /sys/class/net/wwan0/qmi/raw_ip

# use unshare to start a new network (+ mnt and pid) namespace and
# - start separate instance of dbus since modemmanager and networkmanager use it to communicate
# - make several tmpfs mounts for directories that need to be detatched in the new namespace
# - make a bind mount to for resolv.conf associated with current netns
# - start networkmanager and modemmanager
# - start tcpdump to capture traffic on all interfaces
# - create bridge between default and measurement namespace
# - set google dns as default dns in new namespace (note: if mobile network propagates a dns via dhcp they will have higher priority, google dns will be fallback)
# - execute bash
unshare --net=/run/netns/${NSNAME} -mp --fork bash -c '
  mount -t tmpfs nodev /run/dbus/ && dbus-daemon --system --nopidfile
  mount -t tmpfs nodev /etc/NetworkManager/system-connections/
  mount -t tmpfs nodev /run/NetworkManager/
  mount -t tmpfs nodev /run/resolvconf/
  mount --bind /etc/netns/ns_mobileatlas/resolv.conf /etc/resolv.conf
  NetworkManager --debug > /tmp/mobileatlas/NetworkManager.log 2>&1 &
  ModemManager --debug > /tmp/mobileatlas/ModemManager.log 2>&1 &
  tcpdump -i any -n -w /tmp/mobileatlas/traffic.pcap -U 2>&1 &
  ip link add veth0 type veth peer name veth1 netns default
  ip netns exec default ip link set veth1 up
  ip netns exec default ip addr add 10.29.183.2/24 dev veth1
  ip netns exec default ip route add 10.29.183.0/24 dev veth1
  printf "nameserver 8.8.8.8\n" | resolvconf -a veth0.inet
  bash';

# veth0 and veth1 are set to unmanaged in /etc/NetworkManager/NetworkManager.conf, alternativly the following code could be used:
#nmcli dev set veth0 managed no
#nmcli connection delete "Wired connection 1"
#ip link set veth0 down
#ip link set veth0 up
#ip addr add 10.29.183.1/24 dev veth0
#route add default gw 10.29.183.2

#remove veth bridge
ip link delete veth1

#remove iptable rules that were previously created
iptables -D INPUT \! -i veth1 -s 10.29.183.0/24 -j DROP;
iptables -t nat -D POSTROUTING -s 10.29.183.0/24 -o wg+ -j MASQUERADE;

#disable ip forwarding again
sysctl -w net.ipv4.ip_forward=0

#remove mount
umount /run/netns/${NSNAME};
rm /run/netns/${NSNAME};

