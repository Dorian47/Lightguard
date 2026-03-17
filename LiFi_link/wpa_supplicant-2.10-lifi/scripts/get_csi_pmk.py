import socket

import os

import random

import subprocess
import time

import hashlib
from typing import Optional

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 2222



WPA_CLI = "/etc/wpa_supplicant-2.10-lifi/wpa_supplicant/wpa_cli2"
CTRL_DIR = "/run/wpa_supplicant"
IFNAME = "wlp2s0"
NETWORK_ID = os.environ.get("WPA_NETWORK_ID", "0")
SETPSK_ACK_DELAY = float(os.environ.get("SETPSK_ACK_DELAY", "6.0"))
PSK_HASH_FILE = os.environ.get("PSK_HASH_FILE", "/tmp/lifi_psk_hash")
REKEY_TRIGGER_FILE_STA = os.environ.get("REKEY_TRIGGER_FILE_STA", "/tmp/rekey_triggered_sta")
def _derive_psk_hash(passphrase: str) -> str:
    return hashlib.sha256(passphrase.encode("utf-8")).hexdigest()


def _is_hidden_psk(value: str) -> bool:
    value = value.strip().strip('"')
    if not value:
        return True
    return all(ch == "*" for ch in value)


def _wpa_cli_cmd(*args) -> Optional[str]:
    try:
        result = subprocess.run(
            ["sudo", "-n", WPA_CLI, "-i", IFNAME, "-p", CTRL_DIR, *args],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"[STA] wpa_cli failed: {result.stderr.decode().strip()}")
            return None
        return result.stdout.decode(errors="ignore").strip()
    except subprocess.TimeoutExpired:
        print("[STA] wpa_cli timeout")
        return None
    except Exception as e:
        print(f"[STA] Failed to run wpa_cli: {e}")
        return None

def set_lifi_pass(passphrase: str):
    """Set PMK. Returns True on success, False on failure."""
    passphrase = passphrase.strip()
    try:
        result = subprocess.run(
            ["sudo", "-n", WPA_CLI, "-i", IFNAME, "-p", CTRL_DIR, "setpsk", passphrase],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"[STA] wpa_cli setpsk failed: {result.stderr.decode()}")
            return False

        verify = _wpa_cli_cmd("get_network", NETWORK_ID, "psk")
        if not verify or verify.upper() == "FAIL":
            print("[STA] get_network psk hidden/blocked; skip verify")
        else:
            if _is_hidden_psk(verify):
                print("[STA] get_network psk hidden; skip verify")
            else:
                verify = verify.strip().strip('"')
                if verify != passphrase:
                    print("[STA] get_network psk mismatch; reject rekey")
                    return False

        if _wpa_cli_cmd("pmksa_flush") is None:
            print("[STA] pmksa_flush failed; reject rekey")
            return False

        return True
    except subprocess.TimeoutExpired:
        print(f"[STA] wpa_cli setpsk timeout")
        return False
    except Exception as e:
        print(f"[STA] Failed to run wpa_cli: {e}")
        return False



def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((LISTEN_HOST, LISTEN_PORT))
    s.listen(1)
    print(f"[STA] Listening for passphrase on {LISTEN_HOST}:{LISTEN_PORT}")
    while True:
        conn, addr = s.accept()
        try:
            data = conn.recv(128)
            if not data:
                conn.close()
                continue
            passwd = data.decode("utf-8").strip()
            print(f"[STA] Got new passphrase: {passwd!r}")
            # Wait for command to complete before sending ACK
            if set_lifi_pass(passwd):
                if SETPSK_ACK_DELAY > 0:
                    print(f"[STA] Waiting {SETPSK_ACK_DELAY}s before ACK")
                    time.sleep(SETPSK_ACK_DELAY)
                psk_hash = _derive_psk_hash(passwd)
                print(f"[STA] PSK hash: {psk_hash}")
                try:
                    with open(PSK_HASH_FILE, "w", encoding="utf-8") as f:
                        f.write(psk_hash + "\n")
                except Exception as e:
                    print(f"[STA] Failed to write PSK hash file: {e}")
                print("[STA] PMK updated, sending ACK with PSK hash")
                conn.sendall(f"ACK {psk_hash}".encode())
                # Mark rekey triggered for ptk_receiver_sta to monitor handshake result
                try:
                    with open(REKEY_TRIGGER_FILE_STA, "w") as f:
                        f.write(str(time.time()))
                except Exception as e:
                    print(f"[STA] Failed to write rekey trigger file: {e}")
            else:
                print(f"[STA] PMK update failed, sending NACK to AP")
                conn.sendall(b"NACK")
        except Exception as e:
            print(f"[STA] Error handling connection: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    main()

