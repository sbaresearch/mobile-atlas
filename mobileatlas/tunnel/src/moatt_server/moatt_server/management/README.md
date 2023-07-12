# MobileAtlasManagement
The MobileAtlas Management Dashboard provides three views for management interactions with probes: 
- Probe Overview: this view provides an overview of all measurement probes that are currently registered within our management platform. It provides an interface for registering new probes (i.e., activating the token candidate), changing probe names and execute management operations (e.g., push system information, update git repository) on specified target probes.
- Probe Status Information: this view shows details that are specific to a concrete probe (e.g., current temperature, online status history).
- Wireguard Configuration Overview: this view provides information about the registered wireguard clients. Furthermore, it can be used to add additional wireguard endpoints to the current VPN configuration.

## Web Endpoints (REST)

### Endpoints for Probe
- /probe/register
- /probe/poll (token)
- /probe/update_info (token)
- /probe/retrieve (token)

### Endpoints for SIM
- /sim/register
- /sim/poll (token)
- /sim/retrieve (token)

### Endpoints for Admin
- Index -> Dashboard
- activate/deactivate/change_name  of  sim/probe
- send command to Probe

### Token-Authentication for Probe/SIM
1) Probe/SIM registers and retrieves token
   1) When accessing now -> 403
2) Admin activates token
3) Probe/SIM is allowed with Header
   ``` Authorization: Bearer [TOKEN]```

## Example Screenshots

### Probe Overview
![Screenshot of MobileAtlas Dashboard (Probe Overview)](screenshots/dashboard_probes_overview.png?raw=true "MobileAtlas Dashboard (Probe Overview)")

---

### Probe Status Information
![Screenshot of MobileAtlas Dashboard (Probe Status Information)](screenshots/dashboard_probe_status_scaled_to_maxwidth.png?raw=true "MobileAtlas Dashboard (Probe Status Information)")

---

### Wireguard Configuration Overview
![Screenshot of MobileAtlas Dashboard (Wireguard Configuration Overview)](screenshots/dashboard_wireguard_overview_scaled_to_maxwidth.png?raw=true "MobileAtlas Dashboard (Wireguard Configuration Overview)")
