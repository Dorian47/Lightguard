# Overall WiFi + LiFi Project Guide

This document explains how to start the LiFi/WiFi AP and STA from the root directory, and how the PTK is synchronized to the WiFi side after each LiFi rekey.

## 1. High-Level Flow

- The LiFi AP hostapd outputs the PTK via TCP port 8877 after each rekey.
- Root-level scripts launch the LiFi PTK receiver, which automatically forwards the PTK to the WiFi injection scripts.
- WiFi AP listens on port 9899, WiFi STA listens on port 9900, completing PTK installation.

For key port and script details, see:
- [LiFi_link/README.md](LiFi_link/README.md)
- [WiFi_link/README.md](WiFi_link/README.md)

## 2. Configuration Prerequisites

### LiFi Side
- LiFi AP rekey/passphrase distribution logic:
  - [LiFi_link/hostapd-2.10-lifi/scripts/system_manager.py](LiFi_link/hostapd-2.10-lifi/scripts/system_manager.py)
  - Modify STA IP, STA MAC, rekey interval, etc.
- LiFi STA passphrase injection script:
  - [LiFi_link/wpa_supplicant-2.10-lifi/scripts/sta_passphrase.py](LiFi_link/wpa_supplicant-2.10-lifi/scripts/sta_passphrase.py)
  - Modify IFNAME, CTRL_DIR, WPA_CLI path.

### WiFi Side
- WiFi hostapd / wpa_supplicant config file paths and interface names.
- For cross-host PTK injection, use the cross-host scripts in WiFi_link/system_manager.

## 3. PTK Sync Mechanism

- LiFi AP side:
  - [LiFi_link/hostapd-2.10-lifi/scripts/ptk_receiver_ap.py](LiFi_link/hostapd-2.10-lifi/scripts/ptk_receiver_ap.py)
  - Receives PTK -> forwards to WiFi AP (send_ptk_ap.py).
- LiFi STA side:
  - [LiFi_link/wpa_supplicant-2.10-lifi/scripts/ptk_receiver_sta.py](LiFi_link/wpa_supplicant-2.10-lifi/scripts/ptk_receiver_sta.py)
  - Receives PTK -> forwards to WiFi STA (send_ptk_sta.py).

Configurable via environment variables:
- WIFI_SEND_HOST (default 127.0.0.1)
- WIFI_SEND_PORT (AP default 9899, STA default 9900)

## 4. One-Click Startup (Root Directory)

Linux AP side:
- [start_ap.sh](start_ap.sh)
  - Starts LiFi hostapd + LiFi scripts + WiFi hostapd.

Linux STA side:
- [start_sta.sh](start_sta.sh)
  - Starts LiFi wpa_supplicant + LiFi scripts + WiFi wpa_supplicant.
  - Set interface names via LIFI_IFNAME / WIFI_IFNAME environment variables.

## 5. Typical Startup Sequence

1) Run start_ap.sh on the AP machine
2) Run start_sta.sh on the STA machine
3) After the LiFi rekey cycle triggers, PTK will be automatically synced to WiFi

## 6. Troubleshooting

- No PTK injection logs: verify the LiFi PTK receiver script is running.
- WiFi PTK not installed: verify WiFi listening ports match the injection scripts.
- STA cannot update passphrase: check IFNAME / CTRL_DIR / WPA_CLI in sta_passphrase.py.
