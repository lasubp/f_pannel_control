# Grafana dashboard for pcpowerd

Grafana cannot read the local `pcpowerd` Unix socket directly. This optional
exporter reads the daemon's existing `list`, `status`, and `health` actions
and exposes Prometheus metrics. It does not change `pcpowerd`, the CLI, MAAS,
or the web add-on. **Prometheus and Grafana must already be available**;
this installer does not install them.

## 1. Install the exporter on the Raspberry Pi

Copy the `addons/grafana` folder into your project. Once the base
`pcpowerd.service` works, run from the project root:

```bash
sudo bash addons/grafana/install.sh
```

The installer starts `pcpower-exporter.service` and leaves the base daemon
running. Check the result on the Pi:

```bash
systemctl status pcpower-exporter.service
curl http://127.0.0.1:9108/metrics
```

You should see `pcpower_daemon_up 1` and one `pcpower_machine_status_up`
line for each configured machine. The exporter listens on port **9108** on
the Pi's interfaces. Permit TCP 9108 only from your Prometheus server;
the metrics endpoint has no login.

## 2. Add a Prometheus scrape target

Add this job under `scrape_configs` in your **existing** Prometheus config.
Replace the address with your Pi's IP if it differs:

```yaml
  - job_name: pcpower
    scrape_interval: 15s
    scrape_timeout: 10s
    static_configs:
      - targets: ['192.168.9.102:9108']
```

Reload or restart Prometheus using the method appropriate for your own
installation. In Prometheus, check that target `pcpower` is **UP** and query
`pcpower_daemon_up`. The configured target name becomes the Prometheus
`instance` label; the dashboard can filter by it if you add another Pi.

## 3. Import the dashboard

Grafana → **Dashboards** → **New** → **Import dashboard** → upload
`addons/grafana/pcpower-dashboard.json`. Select your existing Prometheus
data source when prompted, then Import. The dashboard refreshes every 30
seconds and defaults to showing all machines. It includes current counts,
power LED history, HDD LED activity, machine read errors, and expander health.

New machines appear automatically in the all-machines graphs after the
daemon reloads its config and Prometheus scrapes again. Reload the dashboard
page to update the Machine filter's dropdown choices.

`pcpower_machine_power_state` is **1 for on** and **0 for off**. If the LED
cannot be read, that series is absent and `pcpower_machine_status_up` is 0;
the dashboard does not turn a read failure into a false off state. HDD activity
is absent for machines without an HDD LED. Metrics are sampled at the
Prometheus scrape interval, so brief LED flashes between scrapes may not be
recorded.

To remove only this bridge:

```bash
sudo systemctl disable --now pcpower-exporter.service
```
