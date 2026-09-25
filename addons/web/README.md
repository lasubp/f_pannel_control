# PC Power web add-on

This optional browser interface uses the existing `pcpowerd` Unix socket. It
does not import the controller or control I²C directly. It can run alongside
`pcpowerctl` and the MAAS add-on. No change to the base daemon is required.

## Install

After the base `pcpowerd.service` is working, place this `addons/web` folder
in your project and run from the project root on the Pi:

```bash
sudo bash addons/web/install.sh
```

The installer copies the web files to `/opt/pcpower`, creates a separate web
password on first run, and starts `pcpower-web.service`. Running it again
updates the web files and **keeps the password**. It does not restart the
base service.

Open `http://<PI-IP>:8766/` in your browser. When prompted for HTTP Basic
credentials, use username **pcpower** and the password printed by:

```bash
sudo cat /etc/pcpower/web-password
```

The page lists machines from `pcpowerd` every five seconds and reads their
power and HDD LED states. Buttons offer Power on, Power off, Reset, direct
Press power and Press reset. Expand **Diagnostics** to read inputs or raw pins.
The top bar offers I²C health, Refresh and Reload config. A daemon config
reload updates the page's machine cards on the next refresh; the web service
does not need to restart. Actions use the existing daemon timeouts and error
responses.

The service listens on all Pi interfaces on TCP port **8766**. Limit access
to your management network with your firewall. HTTP Basic credentials travel
over plain HTTP; use an HTTPS reverse proxy if that network is not trusted.
The page needs JavaScript and a browser that supports `fetch`.

Check status and logs:

```bash
systemctl status pcpower-web.service
journalctl -u pcpower-web.service -f
```

To stop only the web add-on:

```bash
sudo systemctl disable --now pcpower-web.service
```

This leaves `pcpowerd`, `pcpowerctl`, and the MAAS add-on unchanged.
