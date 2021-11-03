## Setup
We use Ansible to new measurement probes.
The script is designed and tested to work with a Raspberry Pi 4 that runs a fresh installation of the [Raspberry Pi OS Lite](https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-32-bit) operating system.

### Initial Patching

normal setup (random password that will be printed to stdout after patching):
```bash
cd mobile-atlas/setup/ansible-bootstrap
ansible-playbook setup-raspis.yml
```

when providing own credentials:
```bash
cd mobile-atlas/setup/ansible-bootstrap
ansible-playbook setup-raspis.yml --extra-vars "new_pw=hunter2"
```

Probes that should be patched during the setup need to be specified in the ansible hosts inventory.
Alternatively, the script can be executed for a dynamic subset of IP addresses.
```bash
ansible-playbook -i 192.168.1.123, setup-raspis.yml
```

### Installing Subsequent Patches
```bash
cd mobile-atlas/setup/ansible-bootstrap
ansible-playbook delay-wg-startup.yml 
ansible-playbook prepare-ns-portforward.yml 
ansible-playbook uhubctrl_pppd.yml
```
