# MAAS add-on

This optional service translates MAAS **Webhook** power requests into the
existing `pcpowerd` Unix-socket protocol. The base daemon and `pcpowerctl`
work without it.

## Install

First install and start your base `pcpowerd.service`. From the **project root**
on the Raspberry Pi, run:

```bash
sudo bash addons/maas/install.sh
```

The script copies this add-on's Python file and systemd unit, creates a
random bearer token once, and starts `pcpower-maas.service`. Running it again
updates the add-on without replacing the token. It does not restart or change
`pcpowerd.service`. It expects the base install to have created the `pcpower`
user/group, `/opt/pcpower/venv/bin/python`, and the default socket at
`/run/pcpower/control.sock`.

Check the service and read the token on the Pi:

```bash
systemctl status pcpower-maas.service
sudo cat /etc/pcpower/maas-token
```

The sample unit listens on port **8765** on all Pi interfaces. Permit that
port from MAAS rack controllers in your firewall. The bearer token travels
over plain HTTP in this setup; use an HTTPS reverse proxy if the connection
crosses an untrusted network.

## Configure each machine in MAAS

Choose power type **Webhook**. Replace `<PI-IP>` with the Pi address reachable
from the MAAS rack controller, and replace `pc1` with the machine name in
`pcpowerd` (not necessarily the MAAS hostname):

| MAAS field | Enter |
| --- | --- |
| URI to power on | `http://<PI-IP>:8765/v1/machines/pc1/on` |
| URI to power off | `http://<PI-IP>:8765/v1/machines/pc1/off` |
| URI to query status | `http://<PI-IP>:8765/v1/machines/pc1/query` |
| Regex to confirm on | `"power_state"\s*:\s*"on"` |
| Regex to confirm off | `"power_state"\s*:\s*"off"` |
| Power token | Contents of `/etc/pcpower/maas-token` |
| Verify SSL connections | No for these `http://` URLs |

Leave the password and user fields empty when using **Power token**. Set both
regex fields; the MAAS defaults expect different response text. For another
PC, change the machine name in all three URLs. The adapter queries the power
LED through `pcpowerd`; it does not keep a separate power-state cache.

Before trying power on/off, test the read-only status endpoint from a host
that can reach the Pi (substitute the token and IP):

```bash
curl -i -H 'Authorization: Bearer YOUR_TOKEN' \
  'http://<PI-IP>:8765/v1/machines/pc1/query'
```

A successful reply is HTTP 200 with `{"power_state":"on"}` or
`{"power_state":"off"}`. If the adapter cannot reach the daemon or read the
LED, it returns an error instead of guessing. MAAS sends POST for power on/off
and GET for query. Its rack controller must be able to reach the Pi.

## Remove only the add-on

```bash
sudo systemctl disable --now pcpower-maas.service
```

This leaves the base daemon and CLI running. Change the power type in MAAS
before relying on it for further machine operations.
