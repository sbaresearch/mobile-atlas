# MobileAtlas SIM Tunnel Server

The MobileAtlas SIM Tunnel Server relays the communication between a measurement probe's modem and a
SIM card hosted on a SIM provider. Additionally, it handles access management, logs relayed
communication and provides information on managed SIM cards.

This directory contains:

* The implementation of the actual server which provides a FastAPI REST interface and a
  server that handles the connections between probes and SIM providers.
* Client implementations for the probe- and the SIM provider sides.
* The `moatt-types` package, which provides types that are shared between the server and
  client implementations.

Details on how SIM Providers and Probes interact with the tunnel server are provided
[here](./Protocol.md).

## Running the Tunnel Server

### Using Nix to build a container image (recommended)

The following snippet can be used to generate a container image and load it into podman:

```bash
cd src/moatt_server
nix build .\#moat-tunnel-server-container
./result | podman load
```

To run, the container needs a valid configuration and access to a TLS
certificate (which can be generated with the Makefile in `../tls-certs`) and key. The
following provides an example of how these can be provided to a container:

```
podman run -d -e MOAT_SIMTUNNEL_CONFIG=./config/config.toml -v <dir containing config>:/app/config:z,ro -v ../tls-certs:/app/ssl:z,ro
```

### Using Nix

Another way to run the server is directly as a Nix app:

Running the tunnel server:

```bash
cd src/moatt_server
nix run .\#moat-tunnel-server -- --config <config-file> &
```

Running the REST API:

```
nix develop
MOAT_SIMTUNNEL_CONFIG=<config-file> gunicorn -k uvicorn.workers.UvicornWorker moatt_server.rest.main:app
```

### Virtualenv

Create a virtualenv using the [Makefile](../Makefile) and activate it:

```bash
cd ..
make
source venv/bin/activate
```

Start the server installed in the venv:

```bash
moat-tunnel-server -- --config <config-file>
```

Finally, use `gunicorn` to run the REST API:

```
MOAT_SIMTUNNEL_CONFIG=<config-file> gunicorn -k uvicorn.workers.UvicornWorker moatt_server.rest.main:app
```

## Tunnel Configuration

An annotated example configuration can be found [here](./example-config.toml).
