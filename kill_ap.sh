#!/usr/bin/env bash
set -euo pipefail

SUDO_BIN="${SUDO_BIN:-sudo}"
"$SUDO_BIN" pkill -f "hostapd|get_pmk.py|system_manager.py|ptk_receiver_ap.py" || true

echo "[AP] Killed AP-side processes."
