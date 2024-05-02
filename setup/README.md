## Setup

We use Ansible to setup new measurement probes.

The Ansible playbook is designed and tested to work with a Raspberry Pi 4
running a patched version of the Raspberry Pi OS Lite operating system. Our
patch does the following: It

* enables the OpenSSH daemon,
* configures the 'pi' user with a random password, and
* stops the root filesystem from growing to use the whole SD card on the first boot,
  instead extending it to a predefined size (thus leaving space giving us
  greater flexibility when
  upgrading probes in the field).

### Patching the Raspberry Pi OS Lite Image

Patching an image already written to a connected SD card:

```bash
cd mobile-atlas/setup
./patch.sh /dev/<boot partition> /dev/<rootfs partition>
```

Patching the downloaded image directly:

```bash
losetup -fLP --show <image>
./patch.sh /dev/loopXp1 /dev/loopXp2
```

### Initial Patching

Normal setup (random password that will be printed to stdout after patching):

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
