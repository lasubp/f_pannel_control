#!/usr/bin/env bash
set -euo pipefail

# Installs only the optional metrics bridge; does not install Prometheus/Grafana.
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if (( EUID != 0 )); then
    echo "Run as root: sudo bash addons/grafana/install.sh" >&2
    exit 1
fi

for file in pcpower_exporter.py pcpower-exporter.service; do
    if [[ ! -f "$SOURCE_DIR/$file" ]]; then
        echo "Missing $SOURCE_DIR/$file" >&2
        exit 1
    fi
done

if ! id pcpower >/dev/null 2>&1 || ! getent group pcpower >/dev/null; then
    echo "Install the base pcpower service first (pcpower user/group missing)." >&2
    exit 1
fi
if [[ ! -x /opt/pcpower/venv/bin/python ]] ||
   [[ ! -d /opt/pcpower ]] ||
   ! systemctl is-active --quiet pcpowerd.service ||
   [[ ! -S /run/pcpower/control.sock ]]; then
    echo "Start and verify pcpowerd.service and its default socket first." >&2
    exit 1
fi

if ! runuser -u pcpower -- /opt/pcpower/venv/bin/python -c \
    'import socket; s = socket.socket(socket.AF_UNIX); s.connect("/run/pcpower/control.sock"); s.close()'; then
    echo "The pcpower user cannot access the daemon socket; check its owner/group." >&2
    exit 1
fi

install -o root -g root -m 0644 "$SOURCE_DIR/pcpower_exporter.py" \
    /opt/pcpower/pcpower_exporter.py
install -o root -g root -m 0644 "$SOURCE_DIR/pcpower-exporter.service" \
    /etc/systemd/system/pcpower-exporter.service

systemctl daemon-reload
systemctl enable pcpower-exporter.service
systemctl restart pcpower-exporter.service
systemctl is-active --quiet pcpower-exporter.service

echo "Metrics available at http://<PI-IP>:9108/metrics"
echo "Next: configure Prometheus scraping and import pcpower-dashboard.json."
