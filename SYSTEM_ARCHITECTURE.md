# WiFi + LiFi Hybrid System Architecture

## System Overview

This system implements a hybrid WiFi/LiFi communication architecture with **synchronized key management**. The LiFi link acts as the **primary secure channel** for key derivation and distribution, while the WiFi link provides **high-bandwidth data transmission** using the synchronized PTK (Pairwise Transient Key).

---

## High-Level Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SYSTEM ARCHITECTURE                                         │
│                              WiFi + LiFi Hybrid Key Synchronization                            │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                │
│   ┌──────────────────────────────────────┐        ┌──────────────────────────────────────┐     │
│   │           AP MACHINE                 │        │           STA MACHINE                │     │
│   │                                      │        │                                      │     │
│   │  ┌────────────────────────────────┐  │        │  ┌────────────────────────────────┐  │     │
│   │  │        LiFi Link (AP)          │  │        │  │       LiFi Link (STA)          │  │     │
│   │  │  ┌──────────────────────────┐  │  │        │  │  ┌──────────────────────────┐  │  │     │
│   │  │  │  hostapd2 (LiFi)         │  │  │  LiFi  │  │  │  wpa_supplicant2 (LiFi)  │  │  │     │
│   │  │  │  - 4-Way Handshake       │◄─┼──┼────────┼──┼─►│  - 4-Way Handshake       │  │  │     │
│   │  │  │  - PTK Generation        │  │  │Wireless│  │  │  - PTK Generation        │  │  │     │
│   │  │  │  - PMK Update (LiFi PSK) │  │  │ Link   │  │  │  - PMK Update (LiFi PSK) │  │  │     │
│   │  │  └───────────┬──────────────┘  │  │        │  │  └───────────┬──────────────┘  │  │     │
│   │  │              │ PTK:8877        │  │        │  │              │ PTK:8877        │  │     │
│   │  │              ▼                 │  │        │  │              ▼                 │  │     │
│   │  │  ┌──────────────────────────┐  │  │        │  │  ┌──────────────────────────┐  │  │     │
│   │  │  │  ptk_receiver_ap.py      │  │  │        │  │  │  ptk_receiver_sta.py     │  │  │     │
│   │  │  │  - Receive PTK           │  │  │        │  │  │  - Receive PTK           │  │  │     │
│   │  │  │  - Forward to WiFi AP    │──┼──┼─ SYNC ─┼──┼──│  - Forward to WiFi STA   │  │  │     │
│   │  │  └───────────┬──────────────┘  │  │ :2223  │  │  └───────────┬──────────────┘  │  │     │
│   │  └──────────────┼─────────────────┘  │        │  └──────────────┼─────────────────┘  │     │
│   │                 │                    │        │                 │                    │     │
│   │                 │ PTK:9899           │        │                 │ PTK:9900           │     │
│   │                 ▼                    │        │                 ▼                    │     │
│   │  ┌────────────────────────────────┐  │        │  ┌────────────────────────────────┐  │     │
│   │  │        WiFi Link (AP)          │  │        │  │       WiFi Link (STA)          │  │     │
│   │  │  ┌──────────────────────────┐  │  │        │  │  ┌──────────────────────────┐  │  │     │
│   │  │  │  hostapd_test (WiFi)     │  │  │  WiFi  │  │  │  wpa_supplicant_test     │  │  │     │
│   │  │  │  - PTK TCP Listener      │◄─┼──┼────────┼──┼─►│  - PTK TCP Listener      │  │  │     │
│   │  │  │  - Install Synced PTK    │  │  │Wireless│  │  │  - Install Synced PTK    │  │  │     │
│   │  │  │  - Data Transmission     │  │  │ Link   │  │  │  - Data Transmission     │  │  │     │
│   │  │  └──────────────────────────┘  │  │        │  │  └──────────────────────────┘  │  │     │
│   │  └────────────────────────────────┘  │        │  └────────────────────────────────┘  │     │
│   └──────────────────────────────────────┘        └──────────────────────────────────────┘     │
│                                                                                                │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### AP Side Components

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  AP SIDE ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐       │
│  │ get_random_time.py  │     │  system_manager.py  │     │  ptk_receiver_ap.py │       │
│  │  (CSI/PMK Server)   │     │  (Rekey Controller) │     │  (PTK Forwarder)    │       │
│  │                     │     │                     │     │                     │       │
│  │  Listen: :9911      │────►│  1. Get CSI/Pass    │     │  Listen: :8877      │       │
│  │  Provide: PMK/Pass  │     │  2. Send to STA     │─────│  Receive: PTK       │       │
│  │                     │     │  3. Trigger Rekey   │     │  Forward: WiFi AP   │       │
│  └─────────────────────┘     └──────────┬──────────┘     └──────────┬──────────┘       │
│                                         │                           │                   │
│                              Passphrase │ :2222                     │ :2223 SYNC       │
│                                         │                           │                   │
│                                         ▼                           ▼                   │
│                              ┌─────────────────────────────────────────────────────┐   │
│                              │                  TO STA MACHINE                     │   │
│                              └─────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                              hostapd2 (LiFi AP)                                  │   │
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────────┐    │   │
│  │  │ TCP Listener      │  │ CSI/PMK Interface │  │ PTK Push                  │    │   │
│  │  │ :7789             │  │ Connect: :9911    │  │ Send to: :8877            │    │   │
│  │  │                   │  │                   │  │                           │    │   │
│  │  │ Cmd: setptk       │  │ Read: 32B PMK     │  │ Push: 48B PTK             │    │   │
│  │  │ <MAC> <PASS>      │  │ from CSI server   │  │ (KCK+KEK+TK)              │    │   │
│  │  └───────────────────┘  └───────────────────┘  └───────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           hostapd_test (WiFi AP)                                 │   │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │   │
│  │  │ PTK TCP Listener on :9899                                                  │  │   │
│  │  │ - Receive PTK from LiFi ptk_receiver_ap.py                                │  │   │
│  │  │ - Install PTK for all associated STAs                                     │  │   │
│  │  │ - Enable encrypted WiFi data transmission                                 │  │   │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### STA Side Components

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  STA SIDE ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                          FROM AP MACHINE                                        │   │
│  └──────────────────────────────────────────────────┬──────────────────────────────┘   │
│                                                      │                                  │
│                               Passphrase :2222       │        SYNC :2223                │
│                                                      │                                  │
│                                                      ▼                                  │
│  ┌─────────────────────┐     ┌─────────────────────────────────────────────────────┐   │
│  │  get_csi_pmk.py     │     │                  ptk_receiver_sta.py                │   │
│  │  (Pass Listener)    │     │                  (PTK Forwarder + Sync)             │   │
│  │                     │     │                                                     │   │
│  │  Listen: :2222      │     │  Listen LiFi PTK: :8877                            │   │
│  │  Receive: Passphrase│     │  Listen AP Sync:  :2223                            │   │
│  │  Action: wpa_cli    │     │  Forward to WiFi: :9900                            │   │
│  │          setpsk     │     │                                                     │   │
│  └──────────┬──────────┘     └──────────────────────────┬──────────────────────────┘   │
│             │                                            │                              │
│             │ wpa_cli setpsk                             │ PTK :9900                    │
│             ▼                                            ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                          wpa_supplicant2 (LiFi STA)                              │   │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │   │
│  │  │ Control Interface Command: SET_LIFI_PASS                                   │  │   │
│  │  │ - Triggered by wpa_cli setpsk command                                     │  │   │
│  │  │ - Update passphrase for PMK re-derivation                                 │  │   │
│  │  │ - Re-derive PMK during 4-Way Handshake MSG1                               │  │   │
│  │  │ - Push PTK to :8877 after successful handshake                            │  │   │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                        wpa_supplicant_test (WiFi STA)                            │   │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │   │
│  │  │ PTK TCP Listener on :9900                                                  │  │   │
│  │  │ - Receive PTK from LiFi ptk_receiver_sta.py                               │  │   │
│  │  │ - Install PTK locally                                                     │  │   │
│  │  │ - Enable encrypted WiFi data transmission                                 │  │   │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE REKEY DATA FLOW                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  [AP MACHINE]                                                       [STA MACHINE]              │
│                                                                                                 │
│  ┌─────────────────┐                                                                           │
│  │ STEP 1          │                                                                           │
│  │ CSI Server      │  Provide CSI/Passphrase                                                   │
│  │ :9911           │─────────────────────┐                                                     │
│  └─────────────────┘                     │                                                     │
│                                          ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: System Manager (Rekey Controller)                                               │   │
│  │                                                                                          │   │
│  │  1. Connect to CSI Server (:9911)         ─────────► Get new passphrase                 │   │
│  │  2. Send passphrase to STA (:2222)        ═══════════════════════════════════════╗      │   │
│  │  3. Wait for ACK + PSK Hash verification                                         ║      │   │
│  │  4. Flush PMKSA cache (hostapd_cli)                                              ║      │   │
│  │  5. Send setptk command (:7789)                                                  ║      │   │
│  └────────────────────────────────────────┬─────────────────────────────────────────╫──────┘   │
│                                           │                                         ║          │
│                              setptk       │                                         ║          │
│                              <MAC> <PASS> │                                         ║          │
│                                           ▼                                         ▼          │
│  ┌─────────────────────────────────────────────────┐       ┌─────────────────────────────────┐ │
│  │ STEP 3: hostapd2 (LiFi AP)                      │       │ get_csi_pmk.py                  │ │
│  │                                                 │       │ Listen: :2222                   │ │
│  │  1. Receive setptk command on :7789             │       │                                 │ │
│  │  2. Update PMK for specified STA MAC            │       │  1. Receive passphrase          │ │
│  │  3. Trigger 4-Way Handshake                     │       │  2. wpa_cli setpsk <pass>       │ │
│  │  4. Generate new PTK                            │       │  3. Flush PMKSA cache           │ │
│  │  5. Push PTK to :8877                           │       │  4. Send ACK + PSK Hash         │ │
│  └─────────────────┬───────────────────────────────┘       └────────────────┬────────────────┘ │
│                    │                                                        │                  │
│       ┌────────────┼────────────────────────────────────────────────────────┼────────────┐     │
│       │            │                                                        │            │     │
│       │            │    LiFi 4-Way Handshake (Wireless)                     │            │     │
│       │            │  ◄═══════════════════════════════════════════════════► │            │     │
│       │            │    MSG1: ANonce                                        │            │     │
│       │            │    MSG2: SNonce + MIC                                  │            │     │
│       │            │    MSG3: GTK + MIC                                     │            │     │
│       │            │    MSG4: ACK                                           ▼            │     │
│       │            │                                       ┌──────────────────────────┐  │     │
│       │            │                                       │ wpa_supplicant2 (LiFi)   │  │     │
│       │            │                                       │                          │  │     │
│       │            │                                       │ - Receive new passphrase │  │     │
│       │            │                                       │ - Re-derive PMK in MSG1  │  │     │
│       │            │                                       │ - Complete handshake     │  │     │
│       │            │                                       │ - Push PTK to :8877      │  │     │
│       └────────────┼───────────────────────────────────────└─────────────┬────────────┘  │     │
│                    │                                                     │               │     │
│                    │ PTK (48 bytes)                       PTK (48 bytes) │               │     │
│                    ▼                                                     ▼               │     │
│  ┌─────────────────────────────────────────┐       ┌─────────────────────────────────────────┐ │
│  │ STEP 4: ptk_receiver_ap.py              │       │ STEP 4: ptk_receiver_sta.py             │ │
│  │                                         │       │                                         │ │
│  │  1. Receive PTK on :8877                │       │  1. Receive PTK on :8877                │ │
│  │  2. Send SYNC to STA (:2223)            │═══════│  2. Wait for AP SYNC                    │ │
│  │  3. Wait for STA READY                  │◄══════│  3. Reply READY                         │ │
│  │  4. Send INSTALL command                │═══════│  4. Receive INSTALL                     │ │
│  │  5. Forward PTK to WiFi AP (:9899)      │       │  5. Forward PTK to WiFi STA (:9900)     │ │
│  └─────────────────┬───────────────────────┘       └──────────────────────┬──────────────────┘ │
│                    │                                                      │                    │
│                    │ PTK                                            PTK   │                    │
│                    ▼                                                      ▼                    │
│  ┌─────────────────────────────────────────┐       ┌─────────────────────────────────────────┐ │
│  │ STEP 5: hostapd_test (WiFi AP)          │       │ STEP 5: wpa_supplicant_test (WiFi STA)  │ │
│  │                                         │       │                                         │ │
│  │  - Receive PTK on :9899                 │       │  - Receive PTK on :9900                 │ │
│  │  - Install PTK for all STAs             │ WiFi  │  - Install PTK locally                  │ │
│  │  - Ready for encrypted communication   │◄═════►│  - Ready for encrypted communication   │ │
│  │                                         │ Data  │                                         │ │
│  └─────────────────────────────────────────┘       └─────────────────────────────────────────┘ │
│                                                                                                 │
│  ════════════════════════════════════════════════════════════════════════════════════════════  │
│                           WiFi ENCRYPTED DATA TRANSMISSION (USING SYNCED PTK)                  │
│  ════════════════════════════════════════════════════════════════════════════════════════════  │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Port Reference Table

| Port  | Location | Direction | Protocol | Purpose |
|-------|----------|-----------|----------|---------|
| 9911  | AP       | hostapd ← CSI Server | TCP | Read CSI/Passphrase/PMK |
| 7789  | AP       | hostapd ← system_manager | TCP | setptk command to trigger rekey |
| 7788  | AP       | hostapd ← control | TCP | General hostapd control |
| 8877  | Both     | hostapd/wpa_supplicant → ptk_receiver | TCP | Push PTK after 4-Way Handshake |
| 2222  | STA      | get_csi_pmk ← system_manager | TCP | Passphrase distribution to STA |
| 2223  | STA      | ptk_receiver_sta ← ptk_receiver_ap | TCP | PTK sync coordination |
| 9899  | AP       | hostapd_test (WiFi) ← ptk_receiver_ap | TCP | PTK injection to WiFi AP |
| 9900  | STA      | wpa_supplicant_test (WiFi) ← ptk_receiver_sta | TCP | PTK injection to WiFi STA |

---

## PTK Format

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PTK STRUCTURE (48 bytes for CCMP)              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────┬────────────────┬────────────────────────────────────┐  │
│  │      KCK       │      KEK       │              TK                    │  │
│  │   (16 bytes)   │   (16 bytes)   │          (16 bytes)                │  │
│  │                │                │                                    │  │
│  │  Key           │  Key           │  Temporal Key                      │  │
│  │  Confirmation  │  Encryption    │  (for data encryption)             │  │
│  │  Key           │  Key           │                                    │  │
│  └────────────────┴────────────────┴────────────────────────────────────┘  │
│                                                                             │
│  Hex String Length: 96 characters (48 bytes × 2)                           │
│                                                                             │
│  For TKIP (tk_len=32): Total 64 bytes = 128 hex characters                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Startup Sequence Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    STARTUP SEQUENCE                                             │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  TIME    [AP MACHINE: start_ap.sh]                [STA MACHINE: start_sta.sh]                  │
│   │                                                                                             │
│   │      ┌────────────────────────────────┐       ┌────────────────────────────────┐           │
│   │  1.  │ Start WiFi hostapd_test        │       │ Start WiFi wpa_supplicant_test │           │
│   │      │ (Listen on :9899)              │       │ (Listen on :9900)              │           │
│   │      └────────────────────────────────┘       └────────────────────────────────┘           │
│   │                    │                                       │                               │
│   │                    │        Wait 20 seconds                │                               │
│   │                    ▼                                       ▼                               │
│   │      ┌────────────────────────────────┐       ┌────────────────────────────────┐           │
│   │  2.  │ Start get_random_time.py       │       │ Start get_csi_pmk.py           │           │
│   │      │ (CSI Server on :9911)          │       │ (Listen on :2222)              │           │
│   │      └────────────────────────────────┘       └────────────────────────────────┘           │
│   │                    │                                       │                               │
│   │                    ▼                                       ▼                               │
│   │      ┌────────────────────────────────┐       ┌────────────────────────────────┐           │
│   │  3.  │ Start ptk_receiver_ap.py       │       │ Start ptk_receiver_sta.py      │           │
│   │      │ (Listen on :8877)              │       │ (Listen on :8877, :2223)       │           │
│   │      └────────────────────────────────┘       └────────────────────────────────┘           │
│   │                    │                                       │                               │
│   │                    ▼                                       │                               │
│   │      ┌────────────────────────────────┐                    │                               │
│   │  4.  │ Start system_manager.py        │                    │                               │
│   │      │ (Rekey loop, interval: 60s)    │                    │                               │
│   │      └────────────────────────────────┘                    │                               │
│   │                    │                                       │                               │
│   │                    ▼                                       ▼                               │
│   │      ┌────────────────────────────────┐       ┌────────────────────────────────┐           │
│   │  5.  │ Start hostapd2 (LiFi AP)       │       │ Start wpa_supplicant2 (LiFi)   │           │
│   │      │ (Control: :7789)               │       │                                │           │
│   │      └────────────────────────────────┘       └────────────────────────────────┘           │
│   │                    │                                       │                               │
│   │                    │◄══════ LiFi Association ══════════════│                               │
│   │                    │                                       │                               │
│   ▼                    │◄══════ 4-Way Handshake ═══════════════│                               │
│                        │                                       │                               │
│  READY                 │◄══════════ Operational ═══════════════│                               │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Rekey Cycle (Periodic Key Refresh)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               PERIODIC REKEY CYCLE (Every 60 seconds)                          │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  STEP 1: Get New Passphrase                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  system_manager.py ──TCP:9911──► get_random_time.py                                      │  │
│  │                                  │                                                        │  │
│  │                                  └──► Returns: CSI-derived passphrase (8 bytes)          │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  STEP 2: Distribute to STA & Verify                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  system_manager.py ──TCP:2222──► get_csi_pmk.py (on STA)                                 │  │
│  │                                  │                                                        │  │
│  │                                  ├──► wpa_cli setpsk <passphrase>                        │  │
│  │                                  ├──► wpa_cli pmksa_flush                                │  │
│  │                                  └──► Returns: "ACK <SHA256_PSK_HASH>"                   │  │
│  │                                                                                           │  │
│  │  system_manager.py verifies PSK hash matches expected value                              │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  STEP 3: Trigger LiFi Rekey                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  system_manager.py ──TCP:7789──► hostapd2 (LiFi AP)                                      │  │
│  │                                  │                                                        │  │
│  │  Command: "setptk <STA_MAC> <passphrase>"                                                │  │
│  │                                  │                                                        │  │
│  │                                  └──► hostapd updates PMK, triggers 4-Way Handshake      │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  STEP 4: LiFi 4-Way Handshake                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  hostapd2 (AP) ◄═════════════════════════════════════════► wpa_supplicant2 (STA)         │  │
│  │                                                                                           │  │
│  │  MSG1: AP → STA (ANonce)                                                                 │  │
│  │        STA re-derives PMK using new passphrase                                           │  │
│  │        STA computes PTK = PRF(PMK, ANonce, SNonce, MAC_AP, MAC_STA)                      │  │
│  │  MSG2: STA → AP (SNonce + MIC)                                                           │  │
│  │  MSG3: AP → STA (GTK + MIC)                                                              │  │
│  │  MSG4: STA → AP (ACK)                                                                    │  │
│  │                                                                                           │  │
│  │  Both sides now have the same PTK                                                        │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  STEP 5: PTK Push & Synchronization                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  hostapd2 ──TCP:8877──► ptk_receiver_ap.py                                               │  │
│  │  wpa_supplicant2 ──TCP:8877──► ptk_receiver_sta.py                                       │  │
│  │                                                                                           │  │
│  │  Sync Protocol:                                                                           │  │
│  │    ptk_receiver_ap ──"SYNC <PTK>"──► ptk_receiver_sta (:2223)                            │  │
│  │    ptk_receiver_ap ◄──"READY"────── ptk_receiver_sta                                     │  │
│  │    ptk_receiver_ap ──"INSTALL"───► ptk_receiver_sta                                      │  │
│  │                                                                                           │  │
│  │  Simultaneous installation to WiFi:                                                       │  │
│  │    ptk_receiver_ap ──PTK──► hostapd_test (:9899)                                         │  │
│  │    ptk_receiver_sta ──PTK──► wpa_supplicant_test (:9900)                                 │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  STEP 6: WiFi Ready for Encrypted Communication                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  hostapd_test (WiFi AP) ◄══════ Encrypted Data ══════► wpa_supplicant_test (WiFi STA)    │  │
│  │                                                                                           │  │
│  │  Both WiFi endpoints now use the same PTK derived from LiFi handshake                    │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════════════════════   │
│  Wait REKEY_INTERVAL (60 seconds), then repeat from STEP 1                                     │
│  ═══════════════════════════════════════════════════════════════════════════════════════════   │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure Reference

```
Overall_Wifi_LiFi_Project/
├── start_ap.sh                    # One-click AP startup script
├── start_sta.sh                   # One-click STA startup script
├── kill_ap.sh                     # Stop AP processes
├── kill_sta.sh                    # Stop STA processes
│
├── LiFi_link/
│   ├── hostapd-2.10-lifi/
│   │   ├── hostapd/
│   │   │   ├── hostapd2           # LiFi AP binary
│   │   │   ├── hostapd_cli2       # LiFi AP CLI tool
│   │   │   └── hostapd2.conf      # LiFi AP configuration
│   │   ├── scripts/
│   │   │   ├── get_pmk.py         # CSI/PMK server (:9911)
│   │   │   ├── get_random_time.py # Random key generator (:9911)
│   │   │   ├── system_manager.py  # Rekey controller
│   │   │   └── ptk_receiver_ap.py # PTK receiver & forwarder (:8877)
│   │   └── src/
│   │       ├── lifi/csi_pmk.c     # CSI/PMK interface
│   │       └── common/wpa_common.c # PTK push logic
│   │
│   └── wpa_supplicant-2.10-lifi/
│       ├── wpa_supplicant/
│       │   ├── wpa_supplicant2    # LiFi STA binary
│       │   └── wpa_cli2           # LiFi STA CLI tool
│       ├── scripts/
│       │   ├── get_csi_pmk.py     # Passphrase listener (:2222)
│       │   └── ptk_receiver_sta.py # PTK receiver & forwarder (:8877, :2223)
│       └── src/rsn_supp/wpa.c     # LiFi passphrase injection
│
└── WiFi_link/
    ├── hostapd-2.10-wifi/
    │   └── hostapd/
    │       └── hostapd_test       # WiFi AP binary (PTK TCP: :9899)
    │
    ├── wpa_supplicant-2.10-wifi/
    │   └── wpa_supplicant/
    │       └── wpa_supplicant_test # WiFi STA binary (PTK TCP: :9900)
    │
    └── system_manager/
        ├── send_ptk_ap.py         # Send PTK to WiFi AP
        ├── send_ptk_sta.py        # Send PTK to WiFi STA
        ├── ap_ptk_sync.py         # Cross-host PTK sync (AP side)
        └── sta_ptk_sync.py        # Cross-host PTK sync (STA side)
```

---

## Security Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SECURITY ARCHITECTURE                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                           KEY DERIVATION HIERARCHY                                        │ │
│  │                                                                                           │ │
│  │    CSI (Channel State Information)                                                        │ │
│  │              │                                                                            │ │
│  │              ▼                                                                            │ │
│  │    ┌─────────────────┐                                                                    │ │
│  │    │   Passphrase    │  8-byte string derived from CSI                                   │ │
│  │    └────────┬────────┘                                                                    │ │
│  │             │                                                                             │ │
│  │             ▼                                                                             │ │
│  │    ┌─────────────────┐                                                                    │ │
│  │    │      PMK        │  Pairwise Master Key (32 bytes)                                   │ │
│  │    │                 │  PMK = PBKDF2(passphrase, SSID, 4096)                             │ │
│  │    └────────┬────────┘                                                                    │ │
│  │             │                                                                             │ │
│  │             │ + ANonce + SNonce + MAC_AP + MAC_STA                                       │ │
│  │             ▼                                                                             │ │
│  │    ┌─────────────────┐                                                                    │ │
│  │    │      PTK        │  Pairwise Transient Key (48 bytes)                                │ │
│  │    │                 │  PTK = PRF-384(PMK, "Pairwise key expansion", ...)                │ │
│  │    │                 │                                                                    │ │
│  │    │  ┌─────┬─────┬──────┐                                                               │ │
│  │    │  │ KCK │ KEK │  TK  │                                                               │ │
│  │    │  │ 16B │ 16B │ 16B  │                                                               │ │
│  │    │  └─────┴─────┴──────┘                                                               │ │
│  │    └─────────────────┘                                                                    │ │
│  │                                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                         DUAL-LINK SECURITY SYNCHRONIZATION                               │ │
│  │                                                                                           │ │
│  │    LiFi Link (Secure Key Exchange)          WiFi Link (High-Speed Data)                 │ │
│  │    ─────────────────────────────────        ────────────────────────────                 │ │
│  │    • Physical layer security (optical)      • Uses synchronized PTK from LiFi           │ │
│  │    • CSI-based key derivation               • No independent key negotiation            │ │
│  │    • Full 4-Way Handshake                   • PTK injected via TCP socket               │ │
│  │    • Generates authentic PTK                • Immediate encrypted data transfer         │ │
│  │                                                                                           │ │
│  │    Advantage: LiFi provides quantum-resistant key exchange                              │ │
│  │    WiFi benefits from high bandwidth without security overhead                          │ │
│  │                                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LIFI_IFNAME` | wlp2s0 | LiFi wireless interface name |
| `WIFI_IFNAME` | wlx90de8088c693 | WiFi wireless interface name |
| `WIFI_SEND_HOST` | 127.0.0.1 | WiFi PTK injection target host |
| `WIFI_SEND_PORT` | 9899 (AP) / 9900 (STA) | WiFi PTK injection target port |
| `STA_SYNC_HOST` | 192.168.2.131 | STA machine IP for sync |
| `STA_SYNC_PORT` | 2223 | PTK sync coordination port |
| `REKEY_INTERVAL` | 60 | Rekey period in seconds |
| `HOSTAPD_CLI` | /etc/hostapd-2.10-lifi/hostapd/hostapd_cli2 | hostapd CLI path |
| `WPA_CLI` | /etc/wpa_supplicant-2.10-lifi/wpa_supplicant/wpa_cli2 | wpa_supplicant CLI path |

---

*Document generated based on source code analysis of the Overall_Wifi_LiFi_Project workspace.*
