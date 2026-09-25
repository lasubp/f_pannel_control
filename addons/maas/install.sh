#!/usr/bin/env bash
set -euo pipefail

# Install only the optional MAAS HTTP adapter. Never install or restart pcpowerd.
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TOKEN_FILE=/etc/pcpower/maas-token

if (( EUID != 0 )); then
    echo "Run as root: sudo bash addons/maas/install.sh" >&2
    exit 1
fi

for file in pcpower_maas.py pcpower-maas.service; do
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

if [[ -L "$TOKEN_FILE" ]] || [[ -e "$TOKEN_FILE" && ! -f "$TOKEN_FILE" ]]; then
    echo "$TOKEN_FILE exists but is not a regular file." >&2
    exit 1
fi

# Group traversal lets the dedicated service user read the bearer token.
install -d -o root -g pcpower -m 0750 /etc/pcpower
install -o root -g root -m 0644 "$SOURCE_DIR/pcpower_maas.py" /opt/pcpower/pcpower_maas.py
install -o root -g root -m 0644 "$SOURCE_DIR/pcpower-maas.service" \
    /etc/systemd/system/pcpower-maas.service

if [[ ! -e "$TOKEN_FILE" ]]; then
    umask 077
    /opt/pcpower/venv/bin/python -c 'import secrets; print(secrets.token_hex(32))' \
        > "$TOKEN_FILE"
    echo "Created a new MAAS bearer token."
else
    echo "Kept the existing MAAS bearer token."
fi

if [[ ! -s "$TOKEN_FILE" ]]; then
    echo "$TOKEN_FILE is empty; refusing to start the adapter." >&2
    exit 1
fi

chown root:pcpower "$TOKEN_FILE"
chmod 0640 "$TOKEN_FILE"

if ! runuser -u pcpower -- /opt/pcpower/venv/bin/python -c \
    'import socket; s = socket.socket(socket.AF_UNIX); s.connect("/run/pcpower/control.sock"); s.close()'; then
    echo "The pcpower user cannot access the daemon socket; check its owner/group." >&2
    exit 1
fi

systemctl daemon-reload
systemctl enable pcpower-maas.service
systemctl restart pcpower-maas.service
systemctl is-active --quiet pcpower-maas.service

echo "MAAS adapter is running on TCP port 8765."
echo "Configure Webhook in MAAS using addons/maas/README.md."
echo "Read the token locally with: sudo cat $TOKEN_FILE"
