
## SIM Provider
### Installing Dependencies

#### Debian

```bash
sudo apt install swig libpcsclite-dev pcscd libbluetooth-dev
```

#### Fedora

```bash
sudo dnf install swig pcsc-lite-devel pcsc-lite bluez-libs-devel
```

### Python Requirements (using virtualenv)

```bash
cd mobile-atlas/mobileatlas/simprovider
virtualenv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Usage

The current version will share all SIM cards that are connected via Serial and PC/SC reader.

The SIM-Provider has two modes:
* In 'direct' mode, it listens on the specified address(es) and
waits for a Probe to connect.
* In 'server' mode, it connects to a
[Tunnel-Server](https://github.com/sbaresearch/mobile-atlas-tunnel) and offers the connected SIMs.

#### Direct Tunnel (probes directly connect to SIM provider)

```bash
cd mobile-atlas
./sim.py -h 0.0.0.0 --cafile <path to CA certificate> direct --cert <certificate> --key <cert key>
```

#### Using the Tunnel-Server

```bash
cd mobile-atlas
API_TOKEN=<token> ./sim.py --host 0.0.0.0 --cafile <path to CA certificate> server --api-url <server endpoint>
```

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

The current version will share all SIM cards that are connected via Serial and PC/SC reader.

The Probe provides two modes:
* In 'direct' mode, it connects directly to a SIM-Provider listening in 'direct' mode.
* In 'server' mode, it connects to a
[Tunnel-Server](https://github.com/sbaresearch/mobile-atlas-tunnel) requesting a connection to the
configured SIM card.

#### Direct Tunnel (directly connect to SIM provider)

```bash
cd mobile-atlas
sudo ./probe.py --host <SIM provider address> --testname TestNetworkInfo --configfile mobileatlas/probe/test_config.json --cafile <path to CA certificate> direct --cert <certificate> --key <cert key>
```

#### Using the Tunnel-Server

```bash
cd mobile-atlas
sudo ./probe.py --host <SIM provider address> --testname TestNetworkInfo --configfile mobileatlas/probe/test_config.json
```
