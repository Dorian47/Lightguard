# LightGuard: Zero-Overhead WiFi Security via Physical-Layer LiFi Key Bootstrapping

---

## Motivation

WiFi eavesdropping is a persistent and fundamental security challenge rooted in a basic physical property of RF: signals propagate omnidirectionally, crossing walls and room boundaries, making every handshake frame observable to any attacker within radio range. The standard WPA2 4-Way Handshake — which establishes the Pairwise Transient Key (PTK) used to encrypt all subsequent WiFi traffic — is therefore conducted over an inherently open channel. Even with strong per-session keys, the negotiation process itself is exposed to passive capture and offline attacks.

**LightGuard** exploits a fundamental asymmetry between RF and optical wireless: *Light Fidelity (LiFi)* transmits data via visible light, which requires strict line-of-sight and cannot penetrate opaque surfaces. This physical confinement makes LiFi an ideal medium for security-sensitive operations that must be hidden from outside observers.

The core insight is simple: **offload key establishment from WiFi to LiFi**. LightGuard equips each node (AP and STA) with both a WiFi NIC and a LiFi transceiver. The LiFi link runs the WPA2 4-Way Handshake and derives the PTK entirely within a physically bounded optical channel. The resulting PTK is then atomically installed on both WiFi interfaces, so the WiFi link carries encrypted application data without ever having negotiated its keys over the air. Cryptographic material never traverses the open RF medium — making passive RF eavesdropping of the key exchange physically impossible.

```
┌──────────────────────────────────────────────────────────┐
│  Traditional WiFi                                        │
│                                                          │
│  AP ──── 4-Way Handshake (RF, open medium) ────► STA    │
│          [Eavesdropper can capture all frames]           │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  LightGuard                                              │
│                                                          │
│  AP ──── 4-Way Handshake (LiFi, line-of-sight) ──► STA  │
│          [Confined by opaque surfaces — key is private]  │
│                                                          │
│  AP ════════ WiFi Data (encrypted with LiFi PTK) ══ STA  │
└──────────────────────────────────────────────────────────┘
```

LightGuard retains all of WiFi's advantages — wide coverage, mobility, high throughput — while eliminating the RF key exposure. Under stable LiFi alignment, rekeying completes transparently: WiFi throughput holds at ~80 Mbps and latency stays ~1 ms through each rekey cycle.

---

## System Overview

Each LightGuard node runs two independent wireless daemons: `hostapd`/`wpa_supplicant` on the LiFi interface for key establishment, and a separate `hostapd`/`wpa_supplicant` on the WiFi interface for data transmission. The LiFi daemons are modified to extract the derived PTK and push it over a local TCP socket, while the WiFi daemons are modified to accept and install an injected PTK without running their own handshake.

### Cross-Link Key Synchronization Protocol

Rekeying proceeds in four phases:

**Phase 1 — Passphrase Distribution:**
The AP generates a fresh random passphrase. `system_manager.py` fetches this passphrase from the local passphrase server (`get_random_time.py`, port 9911) and distributes it to the STA over LiFi (port 2222). The STA injects it into `wpa_supplicant` via `wpa_cli setpsk`.

**Phase 2 — WPA2 4-Way Handshake over LiFi:**
The AP-side `system_manager.py` sends a `setptk` command to LiFi `hostapd` (port 7789) to trigger reauthentication. The standard WPA2 4-Way Handshake executes over the LiFi link, using the shared passphrase to derive a fresh 48-byte PTK (KCK + KEK + TK). Both sides push their derived PTK to `ptk_receiver_ap.py` / `ptk_receiver_sta.py` (port 8877) immediately after the handshake.

**Phase 3 — Two-Phase PTK Synchronization:**
The AP-side receiver initiates a commit protocol with the STA-side receiver (port 2223):
1. AP sends `SYNC <ptk_hex>` → STA replies `READY`
2. AP sends `INSTALL` → STA installs PTK to WiFi STA daemon (port 9900) → STA replies `OK`
3. AP installs PTK to WiFi AP daemon (port 9899)

This two-phase commit ensures both WiFi interfaces switch to the new PTK atomically, preventing any mismatch window.

**Phase 4 — WiFi Data Resumption:**
Both WiFi daemons now share the LiFi-derived PTK and resume encrypted data transmission. No standard WPA2 handshake occurred on the WiFi RF channel.

**Failure Handling:**
If the LiFi handshake fails (e.g., due to physical obstruction or angular misalignment), a watchdog timer detects that no new PTK arrived within the timeout window and immediately disconnects the WiFi link. This prevents the WiFi data channel from continuing with a stale or unverified key. The link recovers automatically once LiFi realignment succeeds and the next rekey completes.

---

## Repository Structure

```
.
├── start_ap.sh              # One-command AP startup
├── start_sta.sh             # One-command STA startup
├── kill_ap.sh               # Tear down all AP processes
├── kill_sta.sh              # Tear down all STA processes
├── SYSTEM_ARCHITECTURE.md  # Detailed port/component diagram
├── MODIFICATIONS.md         # All changes to hostapd/wpa_supplicant source
│
├── LiFi_link/
│   ├── hostapd-2.10-lifi/          # Modified hostapd for LiFi AP
│   │   └── scripts/
│   │       ├── system_manager.py   # Rekey controller: passphrase fetch + distribute + trigger
│   │       ├── ptk_receiver_ap.py  # Receives PTK from hostapd, drives sync, injects to WiFi AP
│   │       ├── get_random_time.py  # Passphrase server (port 9911)
│   │       └── get_pmk.py          # Alternate static passphrase server (testing)
│   └── wpa_supplicant-2.10-lifi/   # Modified wpa_supplicant for LiFi STA
│       └── scripts/
│           ├── sta_passphrase.py   # Passphrase listener (port 2222), calls wpa_cli setpsk
│           └── ptk_receiver_sta.py # Receives PTK from wpa_supplicant, sync server, injects to WiFi STA
│
└── WiFi_link/
    ├── hostapd-2.10-wifi/          # Modified hostapd for WiFi AP (PTK injection via port 9899)
    ├── wpa_supplicant-2.10-wifi/   # Modified wpa_supplicant for WiFi STA (PTK injection via port 9900)
    └── system_manager/             # Cross-host PTK forwarding helpers
        ├── send_ptk_ap.py
        └── send_ptk_sta.py
```

---

## Hardware Requirements

The prototype uses:
- Two mini-PCs running **Ubuntu 22.04**
- Two **Intel AX200** WiFi NICs per node (one for LiFi, one for WiFi)
- A custom **LiFi transceiver frontend** (converts between optical and standard WiFi RF bands, compatible with off-the-shelf IEEE 802.11 NICs)

---

## Configuration

### LiFi AP — `system_manager.py`

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| STA IP | `STA_HOST` | — | IP of the STA machine (required) |
| STA MAC | `STA_MAC` | — | MAC address of LiFi STA NIC (required) |
| Rekey interval | `REKEY_INTERVAL` | 60s | How often to trigger a rekey |
| Handshake timeout | `HANDSHAKE_TIMEOUT` | 30s | WiFi disconnect if no PTK after rekey trigger |
| WiFi interface | `WIFI_INTERFACE` | — | WiFi NIC name on the AP machine |

### LiFi STA — `sta_passphrase.py`

| Parameter | Variable in script | Description |
|-----------|-------------------|-------------|
| `IFNAME` | `IFNAME` | LiFi wpa_supplicant interface name |
| `CTRL_DIR` | `CTRL_DIR` | wpa_supplicant control socket directory |
| `WPA_CLI` | `WPA_CLI` | Path to the modified `wpa_cli2` binary |

### PTK Forwarding (both sides)

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `WIFI_SEND_HOST` | `127.0.0.1` | Host running the WiFi daemon |
| `WIFI_SEND_PORT` | `9899` (AP) / `9900` (STA) | Port for WiFi PTK injection |

For a full port reference, see [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md).

---

## Startup

### AP Machine

```bash
./start_ap.sh
```

This script starts (in order):
1. LiFi `hostapd` on the LiFi NIC
2. `get_random_time.py` — passphrase server (port 9911)
3. `ptk_receiver_ap.py` — PTK receiver + sync coordinator
4. `system_manager.py` — periodic rekey controller
5. WiFi `hostapd` on the WiFi NIC

### STA Machine

```bash
./start_sta.sh
```

This script starts (in order):
1. LiFi `wpa_supplicant` on the LiFi NIC
2. `sta_passphrase.py` — passphrase listener (port 2222)
3. `ptk_receiver_sta.py` — PTK receiver + sync responder
4. WiFi `wpa_supplicant` on the WiFi NIC

> Set `LIFI_IFNAME` and `WIFI_IFNAME` environment variables before running if your interface names differ from the defaults.

### Expected Sequence After Startup

```
[AP] system_manager.py fetches new passphrase from :9911
[AP] Sends passphrase to STA :2222
[STA] sta_passphrase.py injects passphrase via wpa_cli setpsk
[AP] system_manager.py triggers hostapd rekey via setptk :7789
[LiFi] WPA2 4-Way Handshake over LiFi link
[AP] hostapd pushes PTK to ptk_receiver_ap.py :8877
[STA] wpa_supplicant pushes PTK to ptk_receiver_sta.py :8877
[AP↔STA] Two-phase commit: SYNC → READY → INSTALL → OK
[AP] Forwards PTK to WiFi hostapd :9899
[STA] Forwards PTK to WiFi wpa_supplicant :9900
[WiFi] Both sides now share the LiFi-derived PTK — encrypted data resumes
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No PTK injected to WiFi | `ptk_receiver_ap/sta.py` not running | Check startup order; verify port 8877 is listening |
| WiFi PTK install fails | Port mismatch | Verify `WIFI_SEND_PORT` matches WiFi daemon listener (9899 / 9900) |
| STA passphrase not updated | Wrong `IFNAME` or `CTRL_DIR` | Edit `sta_passphrase.py` to match your wpa_supplicant setup |
| Rekey always times out | LiFi link not established | Check LiFi NIC association; verify angular alignment of transceiver |
| WiFi disconnects after rekey | LiFi handshake failed (expected behaviour) | Realign LiFi transceivers; system auto-recovers on next successful rekey |
| `wpa_cli setpsk` returns error | Wrong binary path (`WPA_CLI`) | Point `WPA_CLI` to the modified `wpa_cli2` binary in `wpa_supplicant-2.10-lifi/` |

---

## Related Links

- [LiFi_link/README.md](LiFi_link/README.md) — LiFi subsystem details, port table, compilation
- [WiFi_link/README.md](WiFi_link/README.md) — WiFi subsystem and PTK injection details
- [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Full component and data-flow diagrams
- [MODIFICATIONS.md](MODIFICATIONS.md) — All changes made to hostapd / wpa_supplicant source
