#!/usr/bin/env bash
set -euo pipefail

# Start AP side for LiFi + WiFi and PTK forwarding (Linux)
# Edit paths and configs below to match your setup.

LIFI_ROOT="/etc/hostapd-2.10-lifi"
WIFI_ROOT="/etc/hostapd-2.10-wifi-testing"

# --- LiFi hostapd ---
LIFI_HOSTAPD_BIN="/etc/hostapd-2.10-lifi/hostapd/hostapd2"
LIFI_HOSTAPD_CONF="/etc/hostapd-2.10-lifi/hostapd/hostapd2.conf"

# --- WiFi hostapd ---
WIFI_HOSTAPD_BIN="/etc/hostapd-2.10-wifi-testing/hostapd/hostapd_test"
WIFI_HOSTAPD_CONF="/etc/hostapd-2.10-wifi-testing/hostapd/hostapd_testing.conf"

# --- LiFi scripts ---
LIFI_SCRIPTS="$LIFI_ROOT/scripts"
GET_PMK_SCRIPT="$LIFI_SCRIPTS/get_random_time.py"
PTK_RECV_SCRIPT="$LIFI_SCRIPTS/ptk_receiver_ap.py"
SYS_MGR_SCRIPT="$LIFI_SCRIPTS/system_manager.py"

# Optional: forward PTK to a remote WiFi host
# export WIFI_SEND_HOST=127.0.0.1
# export WIFI_SEND_PORT=9899

SUDO_BIN="${SUDO_BIN:-sudo}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_DIR="${LOG_DIR:-/etc/system_manager_ap}"

KILL_SCRIPT="${KILL_SCRIPT:-$(dirname "$0")/kill_ap.sh}"

mkdir -p "$LOG_DIR"

# Use stdbuf to force line-buffered output for real-time logging
STDBUF="stdbuf -oL -eL"

# Combined log file for all AP processes
LOG_FILE="$LOG_DIR/ap_all.log"

# Clear log file at start
> "$LOG_FILE"

cleanup() {
	echo "[AP] Caught exit signal. Running kill script..."
	if [ -x "$KILL_SCRIPT" ]; then
		"$KILL_SCRIPT"
	else
		echo "[AP] Kill script not found or not executable: $KILL_SCRIPT"
	fi
}

trap cleanup INT TERM EXIT

# ============ Step 1: Start WiFi first ============
echo "[AP] Starting WiFi hostapd..."
$STDBUF "$SUDO_BIN" "$WIFI_HOSTAPD_BIN" "$WIFI_HOSTAPD_CONF" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [hostapd_test (wifi link)] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[AP] Waiting 5 seconds for WiFi to initialize..."
sleep 20

# ============ Step 2: Start LiFi components ============
echo "[AP] Starting LiFi CSI/PMK server..."
$STDBUF "$SUDO_BIN" "$PYTHON_BIN" -u "$GET_PMK_SCRIPT" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [get_random_time.py] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[AP] Starting LiFi PTK receiver (will forward to WiFi)..."
$STDBUF "$SUDO_BIN" "$PYTHON_BIN" -u "$PTK_RECV_SCRIPT" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ptk_receiver_ap.py] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[AP] Starting LiFi system manager (rekey loop)..."
$STDBUF "$SUDO_BIN" "$PYTHON_BIN" -u "$SYS_MGR_SCRIPT" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [system_manager.py] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[AP] Starting LiFi hostapd..."
$STDBUF "$SUDO_BIN" "$LIFI_HOSTAPD_BIN" -d -K "$LIFI_HOSTAPD_CONF" 2>&1 | while IFS= read -r line; do echo "[$(date '+%Y-%m-%d %H:%M:%S')] [hostapd2 (lifi link)] $line"; done | $STDBUF tee -a "$LOG_FILE" &

echo "[AP] Done. Log file: $LOG_FILE"
echo "[AP] Press Ctrl+C to stop displaying logs."
wait
