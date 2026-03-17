#!/usr/bin/env bash
set -euo pipefail

SUDO_BIN="${SUDO_BIN:-sudo}"
"$SUDO_BIN" pkill -f "wpa_supplicant|get_csi_pmk.py|ptk_receiver_sta.py" || true

echo "[STA] Killed STA-side processes."
