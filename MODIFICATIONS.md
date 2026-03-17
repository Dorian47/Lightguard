# Modifications to hostapd / wpa_supplicant 2.10

This document describes all changes made to the original hostapd and wpa_supplicant v2.10 source code to support the LiFi/WiFi hybrid PTK synchronization system.

## hostapd-2.10-lifi

### New Files
- **src/lifi/csi_pmk.c** — PMK TCP interface. Reads a 32-byte PMK from the local passphrase server (127.0.0.1:9911) to supply the key material for the LiFi handshake.

### Modified Files
- **src/common/wpa_common.c** — After computing the PTK during the 4-way handshake, pushes the 48-byte PTK to a local TCP listener (127.0.0.1:8877) so that external scripts can synchronize it to the WiFi link.
- **hostapd/main.c** — Initializes the LiFi TCP listener thread on startup.
- **hostapd/ctrl_iface.c** — Adds the `setptk` command to the LiFi TCP listener (127.0.0.1:7789). Accepts `setptk <sta_mac> <passphrase>` to update the PMK and trigger reauthentication for a specific STA.
- **src/ap/wpa_auth.c** — Supports PMK caching for STAs that have not yet associated, applying the cached PMK once the STA connects.

### Scripts (New)
- **scripts/system_manager.py** — Periodic rekey controller: fetches passphrase from passphrase server, distributes to STA, triggers hostapd rekey.
- **scripts/ptk_receiver_ap.py** — Receives PTK from hostapd, syncs with STA, installs to WiFi AP. Includes watchdog to disconnect WiFi if LiFi handshake fails.
- **scripts/get_random_time.py** — Passphrase TCP server (port 9911). Generates a random passphrase and serves it on demand.

## wpa_supplicant-2.10-lifi

### Modified Files
- **wpa_supplicant/ctrl_iface.c** — Adds the `setpsk` command to wpa_cli. When invoked (`wpa_cli setpsk <passphrase>`), writes the LiFi passphrase via `SET_LIFI_PASS`.
- **src/rsn_supp/wpa.c** — On receiving 4-way handshake msg1, checks if a LiFi passphrase has been set via `SET_LIFI_PASS`. If so, re-derives the PMK from the LiFi passphrase before proceeding with the handshake. Also pushes the computed PTK to 127.0.0.1:8877.

### Scripts (New)
- **scripts/sta_passphrase.py** — STA-side passphrase listener (port 2222). Receives passphrase from the AP system_manager and calls `wpa_cli setpsk` to inject it.
- **scripts/ptk_receiver_sta.py** — Receives PTK from wpa_supplicant, runs sync server for the AP, installs to WiFi STA. Includes watchdog to disconnect WiFi if LiFi handshake fails.

## hostapd-2.10-wifi / wpa_supplicant-2.10-wifi

### Modified Files
- **hostapd/ctrl_iface.c** — Adds a TCP listener (port 9899) that accepts raw 96-character hex PTK strings and directly installs them as the pairwise key for the connected STA.
- **wpa_supplicant/ctrl_iface.c** — Adds a TCP listener (port 9900) that accepts raw 96-character hex PTK strings and directly installs them as the pairwise key.

These WiFi-side modifications allow external key injection without going through the standard 4-way handshake, enabling the LiFi-derived PTK to be applied to the WiFi link.
