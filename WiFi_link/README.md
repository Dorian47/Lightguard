# WiFi_link Usage (hostapd/wpa_supplicant + PTK TCP Injection)

## Overview
This project adds a “local TCP PTK injection” capability to hostapd and wpa_supplicant so the AP/STA sides can synchronize and force-install the same PTK (commonly used for experiments/tests).

Key capabilities:
- **AP side (hostapd)**: listens on `127.0.0.1:9899`, receives PTK, and updates PTK for all associated STAs.
- **STA side (wpa_supplicant)**: listens on `127.0.0.1:9900`, receives PTK, and installs it locally.
- **system_manager** provides scripts to send/sync PTK.

## Structure
- hostapd-2.10-wifi/: modified hostapd sources (PTK TCP listener)
- wpa_supplicant-2.10-wifi/: modified wpa_supplicant sources (PTK TCP listener)
- system_manager/: PTK sender and cross-host sync scripts

## Minimal Call Flow
1. **Build**
   - Follow the README/notes in each directory to build hostapd and wpa_supplicant.
   - Artifacts are typically under each build/ directory.

2. **Start AP (hostapd)**
   - Start hostapd with your existing config.
   - Logs should show: `PTK TCP: listening on 127.0.0.1:9899`.
   - Example command:
     ```
     sudo ./hostapd_test hostapd_testing.conf
     ```

3. **Start STA (wpa_supplicant)**
   - Start wpa_supplicant with your existing config.
   - Logs should show: `PTK TCP: listening on 127.0.0.1:9900`.
   - Example command:
     ```
     sudo ./wpa_supplicant_test -i <wifi_interface> -c wpa_supplicant_testing.conf
     ```

4. **Inject PTK (local or cross-host)**
   - If AP and STA are on the same machine: use `send_ptk_ap.py` and `send_ptk_sta.py` to send to local ports.
   - If AP and STA are on different machines: use `sta_ptk_sync.py` + `ap_ptk_sync.py` for cross-host sync (see below).

## PTK Format
The PTK is a **hex string** in the following format:

```
PTK = KCK(16 bytes) + KEK(16 bytes) + TK(tk_len bytes)
```

- **CCMP (tk_len=16)**: total 48 bytes → 96 hex chars
- **TKIP (tk_len=32)**: total 64 bytes → 128 hex chars

Scripts support an optional prefix: `PTK ` (note the trailing space) for manual input compatibility.

## Script Usage (system_manager)
### 1) Direct Send (same host)
- `send_ptk_ap.py` → send to `127.0.0.1:9899` (AP)
- `send_ptk_sta.py` → send to `127.0.0.1:9900` (STA)

Supported args:
- `<PTK_HEX>`: PTK hex string
- `--prefix`: add `PTK ` prefix before sending

### 2) Cross-host Sync
**STA side (run on STA host):**
- Run `sta_ptk_sync.py` to listen for AP sync requests
- On receipt, it forwards PTK to local `127.0.0.1:9900`

**AP side (run on AP host):**
- Run `ap_ptk_sync.py` to send PTK to STA bridge
- After STA replies OK, AP updates local `127.0.0.1:9899`

**Flow:**
1) AP → STA bridge (TCP 10000 by default)
2) STA bridge → local `127.0.0.1:9900`
3) STA replies OK
4) AP updates local `127.0.0.1:9899`

## Key Implementation Files
- AP PTK TCP: hostapd-2.10-wifi/src/ap/wpa_auth.c
- STA PTK TCP: wpa_supplicant-2.10-wifi/src/rsn_supp/wpa.c
- Sender/bridge scripts: system_manager/*.py

## Troubleshooting
- **No listening log**: ensure you are running binaries built from this project.
- **PTK install fails**: association/handshake must complete so the pairwise cipher is valid.
- **Cross-host failure**: verify STA bridge listen address/port and firewall.

## Notes
- Listen address is fixed to `127.0.0.1` for local-only injection.
- Ports are hard-coded (AP: 9899, STA: 9900).
