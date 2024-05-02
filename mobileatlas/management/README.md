# MobileAtlas Management Server

This directory contains the server implementation used to manage and monitor the
MobileAtlas probes. Specifically, it handles probe authentication, deploys Wireguard
configurations to probes, monitors each probe's status, and serves as the default
authentication/authorization backend for the SIM tunnel server.

All this is administered through a simple web UI.

## Running

### Using Nix to build a container image (recommended)

The following can be used to build a container image and load it into podman.

```bash
nix build .\#moat-management-image
./result | podman load
```

To add a configuration file to the container, use a bind mount and set the
`MOAT-MANAGEMENT-CONFIG` environment variable. E.g.:

```
podman run -d -e MOAT-MANAGEMENT-CONFIG=./config/config.toml -v <directory-containing-config>:/app/config:z,ro localhost/mobile-atlas-management
```

### Using Nix

Another way to run the server is directly as a Nix app:

```bash
nix run . -- --config <config-file>
```


### Virtualenv

**TODO**

## Configuration

An annotated example configuration file can be found [here](./example-config.toml).

## Authentication Flow

We now describe the authentication flow for probes and SIM-providing clients.

### Probes

To register, probes first send a generated token, their MAC address, and the requested
token scope to the `/tokens/register` endpoint. The scope can be one of *Wireguard*,
*Probe*, or *Both* and determines what functionality will be accessible once the token
is approved. Next, an admin has to manually approve the registered token using the web
UI. Once the token has been accepted, the probe can start using the API.

#### SIM Tunnel registration

Probes that successfully registered a token with the *Probe* scope can use that token to
register with the SIM tunnel using a SIM tunnel token, which determines which SIM cards
the probe will be able to access. To register, the probe makes a POST request to the
`/tunnel/probe` endpoint and includes a SIM tunnel token.

```
POST /tunnel/probe HTTP/1.1
...
Authorization: Bearer <management server access token>
Content-Type: application/json

{"token": <tunnel server token>}
```

When the registration is successful, the server returns a session token that can then be
used to interact with the SIM tunnel server.


### SIM Providers

Currently SIM Providers only need a SIM tunnel token to register with the management
server and retrieve a session token usable with the SIM tunnel. To register a SIM
provider simply sends a post request to the `/tunnel/provider` endpoint.

```
POST /tunnel/provider HTTP/1.1
...
Authorization: Bearer <tunnel server token>


```
