#!/usr/bin/env bash
set -euo pipefail

# Install only the optional web UI. Never install or restart pcpowerd.
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PASSWORD_FILE=/etc/pcpower/web-password

if (( EUID != 0 )); then
    echo "Run as root: sudo bash addons/web/install.sh" >&2
    exit 1
fi

for file in pcpower_web.py pcpower-web.service web/index.html web/app.js web/style.css; do
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

if [[ -L "$PASSWORD_FILE" ]] ||
   [[ -e "$PASSWORD_FILE" && ! -f "$PASSWORD_FILE" ]]; then
    echo "$PASSWORD_FILE exists but is not a regular file." >&2
    exit 1
fi

install -d -o root -g pcpower -m 0750 /etc/pcpower
install -d -o root -g root -m 0755 /opt/pcpower/web
install -o root -g root -m 0644 "$SOURCE_DIR/pcpower_web.py" \
    /opt/pcpower/pcpower_web.py
install -o root -g root -m 0644 "$SOURCE_DIR/pcpower-web.service" \
    /etc/systemd/system/pcpower-web.service
for file in index.html app.js style.css; do
    install -o root -g root -m 0644 "$SOURCE_DIR/web/$file" "/opt/pcpower/web/$file"
done

if [[ ! -e "$PASSWORD_FILE" ]]; then
    umask 077
    /opt/pcpower/venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))' \
        > "$PASSWORD_FILE"
    echo "Created a new web UI password."
else
    echo "Kept the existing web UI password."
fi

if [[ ! -s "$PASSWORD_FILE" ]]; then
    echo "$PASSWORD_FILE is empty; refusing to start the web UI." >&2
    exit 1
fi
chown root:pcpower "$PASSWORD_FILE"
chmod 0640 "$PASSWORD_FILE"

if ! runuser -u pcpower -- /opt/pcpower/venv/bin/python -c \
    'import socket; s = socket.socket(socket.AF_UNIX); s.connect("/run/pcpower/control.sock"); s.close()'; then
    echo "The pcpower user cannot access the daemon socket; check its owner/group." >&2
    exit 1
fi

systemctl daemon-reload
systemctl enable pcpower-web.service
systemctl restart pcpower-web.service
systemctl is-active --quiet pcpower-web.service

echo "Web UI is running at http://<PI-IP>:8766/"
echo "Log in as pcpower; read the password with: sudo cat $PASSWORD_FILE"
