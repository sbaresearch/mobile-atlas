# Protocol

This document explains how clients (both SIM providers and probes) interact with the
tunnel server to establish a SIM tunnel. What this document does NOT describe is how
clients initially register to receive the session tokens necessary to access the tunnel
server as that is handled by pluggable auth handlers. At the moment the only built-in
auth handler uses the MobileAtlas management server to handle this initial registration.

## Protocol Flow

After having completed the auth handler specific registration flow the clients can
connect to the tunnel server. Clients that want to provide SIM cards to the system have
to identify the SIM cards they want to provide. They do so by making a PUT request to
the `/provider/sims` REST endpoint containing a JSON list of SIM cards (The *imsi* and
*iccid* keys are optional):

```
PUT /provider/sims HTTP/1.1
...
Authorization: Bearer <session token>
Content-Type: application/json

[{"id": <integer ID>, "imsi": <SIM IMSI>, "iccid": <SIM ICCID>}, ...]
```

The `ID` field is the primary identifier used to refer to each SIM card and can be
freely chosen by a client.

After successfully registering the provided SIM cards the SIM providing client then
connects to the server using the tunnel protocol (as described in the next section)
and waits for connection requests. If there is a change in which SIM cards are provided
the client can simply send another PUT request with the updated list of SIM cards.

Clients wanting to establish a tunnel to a SIM card do not have to do any additional
setup and can just connect to the server using the protocol flow described in the next
section.

### Tunnel Protocol Flow

```
< TCP/TLS handshake >
Provider              Server                  Probe
| <- TCP/TLS handsh. -> | <- TCP/TLS handsh. -> |
| -- AuthRequest -----> | <- AuthRequest ------ |
| <- AuthResponse ----- | -- AuthResponse ----> |
|                       | <- ConnectRequest --- |
| <- ConnectRequest --- |                       |
| -- ConnectResponse -> |                       |
|                       | -- ConnectResponse -> |
| <- ApduPacket ------> | <- ApduPacket ------> |
:                       :                       :
```

## Serialization Formats

### ApduPacket

```
 0
 0 1 2 3 4 5 6 7 
+---------------+
|  version = 1  |
+---------------+
|    opcode     |
+---------------+
|               |
|    length     |
|               |
|               |
+---------------+
|    payload    |
.               .
.               .
+---------------+
```

* *version*: Protocol version.
* *opcode*:
  * 0: payload contains APDU
  * 1: Reset (payload should be empty)
* *length*: length of the payload
* *payload*: data

### AuthRequest
```
 0 1 2 3 4 5 6 7 8
+-----------------+
|   version = 1   |
+-----------------+
|    auth_type    |
+-----------------+
|     length      |
|                 |
+-----------------+
|      token      |
.                 .
.                 .
+-----------------+
```

* *version*: protocol version
* *auth_type*: type of connecting client
  * 1: SIM provider
  * 2: Probe
* *length*: length of token
* *token*: access token

### AuthResponse

```
 0 1 2 3 4 5 6 7 8
+-----------------+
|   version = 1   |
+-----------------+
|     status      |
+-----------------+
```

* *version*: protocol version
* *status*: Response status.
  * 0: Success
  * 1: Unauthorized 
  * 2: NotRegistered

### ConnectRequest

```
 0 1 2 3 4 5 6 7 8
+-----------------+
|   version = 1   |
+-----------------+
|      flags      |
+-----------------+
|   ident_type    |
+-----------------+
|   identifier    |
.                 .
.                 .
+-----------------+
```

* *version*: protocol version
* *flags*:
  * 1: Do not wait for SIM card
    to become available if it is
    not immediately available.
* *ident_type*: the type of identifier used
* *identifier*: identifies the requested SIM card.

### ConnectResponse

```
 0 1 2 3 4 5 6 7 8
+-----------------+
|   version = 1   |
+-----------------+
|     status      |
+-----------------+
```

* *version*: protocol version
* *status*: Response status.
  * 0: Success
  * 1: NotFound 
  * 2: Forbidden
  * 3: NotAvailable
  * 4: ProviderTimedOut
