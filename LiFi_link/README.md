# LiFi Link Guide (hostapd / wpa_supplicant 2.10-lifi)

This guide describes the LiFi-modified hostapd and wpa_supplicant, covering overall functionality, port/script relationships, and the complete run flow.

## 1. Directory Structure

- hostapd-2.10-lifi/
  - hostapd/: Main binary and control interface
  - src/: Core protocol stack (with LiFi extensions)
  - scripts/: Local key management and control scripts
- wpa_supplicant-2.10-lifi/
  - wpa_supplicant/: Main binary and control interface
  - src/: Core protocol stack (with LiFi extensions)
  - scripts/: STA-side passphrase listener and injection scripts

## 2. LiFi Feature Overview

### hostapd Side
1) LiFi TCP Listener (127.0.0.1:7789)
   - Accepts format: setptk <sta_mac> <passphrase>
   - If STA is associated: updates PMK and triggers reauth
   - If STA is not associated: caches the value until association

2) CSI/PMK Interface
   - src/lifi/csi_pmk.c: reads 32-byte PMK from 127.0.0.1:9911

3) PTK Push
   - src/common/wpa_common.c: sends 48-byte PTK to 127.0.0.1:8877

### wpa_supplicant Side
1) Control Interface Command: SET_LIFI_PASS
   - Triggered by wpa_cli setpsk command
   - Writes the LiFi passphrase and re-derives PMK during handshake

2) LiFi Passphrase Injection
   - src/rsn_supp/wpa.c: re-derives PMK during 4-way handshake msg1

### Script Interactions
- hostapd/scripts/get_pmk.py
  - Provides CSI/passphrase TCP service (default port 9911)
- hostapd/scripts/ptk_receiver_ap.py
  - Receives PTK and writes to /tmp/ap_ptk.bin
- hostapd/scripts/system_manager.py
  - Periodic loop: fetch CSI -> distribute STA passphrase -> trigger hostapd rekey
- wpa_supplicant/scripts/get_csi_pmk.py
  - STA-side passphrase listener that calls wpa_cli setpsk

## 3. Ports and Data Flow

| Port | Direction | Purpose |
|------|-----------|---------|
| 9911 | hostapd <- CSI server | Reads CSI/passphrase/PMK |
| 7789 | hostapd <- system_manager | setptk triggers rekey |
| 8877 | hostapd -> ptk_receiver | Pushes PTK |
| 2222 | STA <- system_manager | Distributes passphrase |

Default addresses are 127.0.0.1 (loopback). For STA passphrase distribution, configure the real STA IP.

## 4. Compilation

### hostapd
Build in hostapd-2.10-lifi/hostapd:

- Produces hostapd2 / hostapd_cli2
- Makefile already includes LiFi source files

Example:
- cd hostapd-2.10-lifi/hostapd
- make

### wpa_supplicant
Build in wpa_supplicant-2.10-lifi/wpa_supplicant:

- Produces wpa_supplicant / wpa_cli2

Example:
- cd wpa_supplicant-2.10-lifi/wpa_supplicant
- make

> Check the .config / defconfig in each directory for specific build options.

## 5. Required Configuration

### hostapd/scripts/system_manager.py
Modify these variables:
- STA_HOST: real IP of the STA
- mac_str: MAC address of the STA to rekey
- REKEY_INTERVAL: rekey period (seconds)

### wpa_supplicant/scripts/get_csi_pmk.py
Modify these variables:
- IFNAME: STA wireless interface name
- CTRL_DIR: wpa_supplicant control socket directory
- WPA_CLI: path to wpa_cli2

## 6. Recommended Startup Order

1) Start CSI service (hostapd side)
   - hostapd-2.10-lifi/scripts/get_pmk.py

2) Start PTK receiver (hostapd side)
   - hostapd-2.10-lifi/scripts/ptk_receiver_ap.py

3) Start hostapd
   - Use your hostapd.conf

4) Start STA passphrase listener
   - wpa_supplicant-2.10-lifi/scripts/get_csi_pmk.py

5) Start system_manager (periodic control)
   - hostapd-2.10-lifi/scripts/system_manager.py

## 7. Manual Trigger and Debugging

### Manually Set STA Passphrase
On the STA, run:
  wpa_cli2 setpsk <passphrase>

This triggers SET_LIFI_PASS, causing wpa_supplicant to use the new LiFi passphrase.

### Manually Trigger hostapd Rekey
Send to 127.0.0.1:7789:
  setptk <sta_mac> <passphrase>

hostapd will update the PMK and attempt to trigger reauth.

## 8. Troubleshooting

1) STA cannot update key
   - Verify get_csi_pmk.py is running on the STA
   - Verify IFNAME / CTRL_DIR / WPA_CLI paths are correct

2) hostapd does not respond to setptk
   - Check hostapd startup logs for successful LiFi listener initialization
   - Verify REKEY_HOST/PORT in system_manager

3) PTK not written to disk
   - Verify ptk_receiver_ap.py is running
   - Verify port 8877 is not occupied

## 9. Security Notice

This implementation is intended for experimental/research environments:
- Passphrase/PMK/PTK are transmitted in plaintext over localhost
- No authentication or encrypted transport is implemented
- Only recommended for isolated test networks

For production use, add authentication, encryption, and access control.
