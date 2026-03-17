PTK TCP Sender Scripts (AP/STA)

Overview
- AP listens on 127.0.0.1:9899
- STA listens on 127.0.0.1:9900
- Payload is a hex string for PTK: KCK(16 bytes) + KEK(16 bytes) + TK(tk_len bytes)
- For CCMP (tk_len=16): 32 + 16 = 48 bytes => 96 hex characters
- For TKIP (tk_len=32): 64 bytes => 128 hex characters

Example PTK (CCMP, 96 hex chars)
KCK: 00112233445566778899aabbccddeeff
KEK: 0102030405060708090a0b0c0d0e0f10
TK : aabbccddeeff00112233445566778899
PTK hex (concat):
00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899

Usage (AP)
- python send_ptk_ap.py <PTK_HEX>
- python send_ptk_ap.py --prefix <PTK_HEX>
Examples (AP)
- python send_ptk_ap.py
- python send_ptk_ap.py 00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899
- python send_ptk_ap.py --prefix 00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899

Usage (STA)
- python send_ptk_sta.py <PTK_HEX>
- python send_ptk_sta.py --prefix <PTK_HEX>
Examples (STA)
- python send_ptk_sta.py
- python send_ptk_sta.py 00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899
- python send_ptk_sta.py --prefix 00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899

Notes
- AP and STA must receive the same PTK to keep traffic working.
- Use --prefix if you want to send with "PTK " prefix.

AP/STA Sync (TCP Bridge)
STA side (run on STA host):
- python sta_ptk_sync.py --listen 0.0.0.0 --port 10000

AP side (run on AP host):
- python ap_ptk_sync.py
- python ap_ptk_sync.py 00112233445566778899aabbccddeeff0102030405060708090a0b0c0d0e0f10aabbccddeeff00112233445566778899
- python ap_ptk_sync.py --sta-host 192.168.1.151 --sta-port 10000

Flow:
1) AP sends PTK to STA bridge (STA forwards to local 127.0.0.1:9900).
2) STA bridge replies OK.
3) AP updates local PTK via 127.0.0.1:9899.
