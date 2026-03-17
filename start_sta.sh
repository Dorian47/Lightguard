#!/usr/bin/env bash
set -euo pipefail

# Start STA side for LiFi + WiFi and PTK forwarding (Linux)
# Edit paths and interfaces below to match your setup.

LIFI_ROOT="/etc/wpa_supplicant-2.10-lifi"
WIFI_ROOT="/etc/wpa_supplicant-2.10-test"

LIFI_IFNAME="${LIFI_IFNAME:-wlp2s0}"
# TODO: Set your WiFi interface name
WIFI_IFNAME="${WIFI_IFNAME:-wlx90de8088c693}"

# --- LiFi wpa_supplicant ---
LIFI_WPA_BIN="/etc/wpa_supplicant-2.10-lifi/wpa_supplicant/wpa_supplicant2"
LIFI_WPA_CONF="/etc/wpa_supplicant-2.10-lifi/wpa_supplicant/wpa_supplicant2.conf"

# --- WiFi wpa_supplicant ---
WIFI_WPA_BIN="/etc/wpa_supplicant-2.10-test/wpa_supplicant/wpa_supplicant_test"
WIFI_WPA_CONF="/etc/wpa_supplicant-2.10-test/wpa_supplicant/wpa_supplicant_testing.conf"

# --- LiFi scripts ---
LIFI_SCRIPTS="$LIFI_ROOT/scripts"
GET_PASS_SCRIPT="$LIFI_SCRIPTS/get_csi_pmk.py"
PTK_RECV_SCRIPT="$LIFI_SCRIPTS/ptk_receiver_sta.py"

# Optional: forward PTK to a remote WiFi host
# export WIFI_SEND_HOST=127.0.0.1
# export WIFI_SEND_PORT=9900

SUDO_BIN="${SUDO_BIN:-sudo}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_DIR="${LOG_DIR:-/etc/system_manager_sta}"

KILL_SCRIPT="${KILL_SCRIPT:-$(dirname "$0")/kill_sta.sh}"

mkdir -p "$LOG_DIR"

# Use stdbuf to force line-buffered output for real-time logging
STDBUF="stdbuf -oL -eL"

# Combined log file for all STA processes
LOG_FILE="$LOG_DIR/sta_all.log"

# Clear log file at start
> "$LOG_FILE"

cleanup() {
	echo "[STA] Caught exit signal. Running kill script..."
	if [ -x "$KILL_SCRIPT" ]; then
		"$KILL_SCRIPT"
	else
		echo "[STA] Kill script not found or not executable: $KILL_SCRIPT"
	fi
}

trap cleanup INT TERM EXIT

# ============ Step 1: Start WiFi first ============
echo "[STA] Starting WiFi wpa_supplicant..."
$STDBUF "$SUDO_BIN" "$WIFI_WPA_BIN" -i "$WIFI_IFNAME" -c "$WIFI_WPA_CONF" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [wpa_supplicant_test (wifi link)] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[STA] Waiting 20 seconds for WiFi to initialize..."
sleep 20

# --- Restore static IP for the WiFi interface (set by user) ---
# TODO: Set WIFI_STATIC_IP to match your network configuration
WIFI_STATIC_IP="${WIFI_STATIC_IP:-192.168.1.151}"
echo "[STA] Restoring static IP $WIFI_STATIC_IP to $WIFI_IFNAME"
$SUDO_BIN ifconfig "$WIFI_IFNAME" "$WIFI_STATIC_IP" || echo "[STA] Failed to set static IP on $WIFI_IFNAME"

# ============ Step 2: Start LiFi components ============
echo "[STA] Starting LiFi passphrase listener..."
$STDBUF "$SUDO_BIN" "$PYTHON_BIN" -u "$GET_PASS_SCRIPT" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [get_csi_pmk.py] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[STA] Starting LiFi PTK receiver (will forward to WiFi)..."
$STDBUF "$SUDO_BIN" "$PYTHON_BIN" -u "$PTK_RECV_SCRIPT" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ptk_receiver_sta.py] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[STA] Starting LiFi wpa_supplicant..."
$STDBUF "$SUDO_BIN" "$LIFI_WPA_BIN" -d -K -i "$LIFI_IFNAME" -c "$LIFI_WPA_CONF" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [wpa_supplicant2 (lifi link)] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[STA] Done. Log file: $LOG_FILE"
echo "[STA] Press Ctrl+C to stop displaying logs."
wait
