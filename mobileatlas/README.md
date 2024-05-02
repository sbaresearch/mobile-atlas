
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
* In 'server' mode, it connects to a [Tunnel-Server](tunnel/README.md) and offers the
connected SIMs.

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
* In 'server' mode, it connects to a [Tunnel-Server](tunnel/README.md) requesting a
connection to the configured SIM card.

#### Direct Tunnel (directly connect to SIM provider)

```bash
cd mobile-atlas
sudo ./probe.py --host <SIM provider address> --testname TestNetworkInfo --configfile mobileatlas/probe/test_config.json --cafile <path to CA certificate> direct --cert <certificate> --key <cert key>
```

#### Using the Tunnel-Server

```bash
cd mobile-atlas
MAM_TOKEN=<token for management server> API_TOKEN=<SIM tunnel token> sudo ./probe.py --host <SIM provider address> --testname TestNetworkInfo --configfile mobileatlas/probe/test_config.json
```

#### Test Config

A json formatted config file containing the experiment's configuration parameters has to be provided when executing the probe.
`test_config.json`:
```json
{
    "imsi" : 123456789012345,
    "phone_number": "+1234567890",
    "provider_name": "AT_MobileAtlasTest",
    "module_blacklist" : ["qmi_wwan", "cdc_ether"],
    "test_params": {
        "apn" : "internet",
        "pdp_type" : "ipv4v6"
    }
}
```

The allowed configuration options are defined
[here](probe/measurement/test/test_args.py) and can be further extended by every
specific experiment (cf. function `validate_test_config` in
[this](probe/measurement/test/test_network_base.py) file).

## SIM Tunnel Server

The SIM tunnel server is responsible for connecting probes with SIM providers and
handles the authentication/authorization of providers and probes.

For more details and instructions on using the SIM tunnel server, please refer to the
relevant [README](tunnel/README.md).

## Management Server

The management server is used to manage and monitor the MobileAtlas probes.
Specifically, it handles the authentication of probes, the deployment of Wireguard
configurations to probes, monitors the status of each probe, and serves as the default
authentication/authorization backend for the SIM tunnel server.

Please refer to the [README](management/README.md) for more information.

## TLS certificate generation

If you need a quick way to generate certificates for the clients/servers you can
use the Makefile provided in the `tls-certs` directory.
