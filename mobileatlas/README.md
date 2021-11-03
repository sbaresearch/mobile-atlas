
## SIM Provider
### Installing Dependencies

```bash
sudo apt install swig libpcsclite-dev pcscd libbluetooth-dev
```

### Python Requirements (using virtualenv)

```bash
cd mobile-atlas/mobileatlas/simprovider
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Usage
```bash
cd mobile-atlas
./sim.py
```
The current version will share all SIM cards that are connected via Serial and PC/SC reader.

## Measurement Probe

### Setup Procedure
The setup procedure for patching a Raspberry Pi 4 is explained in [this](../setup) README file.

### Python Requirements (using virtualenv)

```bash
cd mobile-atlas/mobileatlas/probe
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```


### Usage

```bash
cd mobile-atlas
sudo ./probe.py --host 192.168.1.123 --testname TestNetworkInfo --configfile mobileatlas/probe/test_config.json
```
