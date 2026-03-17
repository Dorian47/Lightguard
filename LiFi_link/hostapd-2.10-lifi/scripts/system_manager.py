import os
import time
import socket
import threading
import traceback
import hashlib
import subprocess

CSI_HOST = '127.0.0.1'
CSI_PORT = 9911

HOSTAPD_HOST = '127.0.0.1'
HOSTAPD_PORT = 7788

# TODO: Set the real IP of the STA for passphrase distribution
STA_HOST = os.environ.get("STA_HOST", "192.168.2.131")
STA_PORT = 2222

REKEY_HOST = '127.0.0.1'
REKEY_PORT = 7789

REKEY_INTERVAL = 60

# WiFi disconnect settings
WIFI_INTERFACE = os.environ.get("WIFI_INTERFACE", "wlx90de8088c692")
REKEY_TRIGGER_FILE = os.environ.get("REKEY_TRIGGER_FILE", "/tmp/rekey_triggered")

HOSTAPD_CLI = os.environ.get(
    "HOSTAPD_CLI",
    "/etc/hostapd-2.10-lifi/hostapd/hostapd_cli2",
)
HOSTAPD_CTRL_DIR = os.environ.get("HOSTAPD_CTRL_DIR", "/var/run/hostapd2")
HOSTAPD_IFNAME = os.environ.get("HOSTAPD_IFNAME", "wlp2s0")

latest_passphrase = "00000000"
# TODO: Set the MAC address of the STA to rekey
mac_str = os.environ.get("STA_MAC", "e0:2b:e9:f6:16:3e")
# TODO: Set the real IP of the STA
sta_ip = os.environ.get("STA_HOST", "192.168.2.131")

#get old password to send
def get_passphrase():
    """Fetch new passphrase. Returns True on success, False on failure."""
    global latest_passphrase
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((CSI_HOST, CSI_PORT))
            passwd = s.recv(64).decode('ascii')
            if not passwd:
                print(f"[SystemManager] Got empty passphrase from CSI")
                return False
            print(f"[SystemManager] Got passphrase from CSI: {passwd}")
            latest_passphrase = passwd
            return True
    except socket.timeout:
        print(f"[SystemManager] Timeout connecting to CSI server")
        return False
    except Exception as e:
        print(f"[SystemManager] Failed to get passphrase from CSI: {e}")
        return False


def send_rekey():
    try:    
        #print("gugugaga")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((REKEY_HOST, REKEY_PORT))
            cmd = "setptk {} {}\n".format(mac_str,latest_passphrase)
            s.sendall(cmd.encode())
            print(f"[SystemManager] send rekey command" + cmd)
            s.close()
    except Exception as e:
        print(f"[!] Failed to send rekey cmd:  {e}")


def mark_rekey_triggered():
    """Write rekey trigger timestamp for ptk_receiver to monitor handshake result"""
    try:
        with open(REKEY_TRIGGER_FILE, "w") as f:
            f.write(str(time.time()))
        print(f"[SystemManager] Rekey trigger marked at {REKEY_TRIGGER_FILE}")
    except Exception as e:
        print(f"[SystemManager] Failed to write rekey trigger file: {e}")


def disconnect_wifi_link():
    """Disconnect WiFi link - protects WiFi when LiFi rekey fails"""
    try:
        result = subprocess.run(
            ["iw", "dev", WIFI_INTERFACE, "station", "dump"],
            capture_output=True, timeout=2
        )
        stations = []
        for line in result.stdout.decode().split('\n'):
            line = line.strip()
            if line.startswith('Station'):
                parts = line.split()
                if len(parts) >= 2:
                    stations.append(parts[1])
        if not stations:
            print(f"[SystemManager] No WiFi STAs to disconnect")
            return
        for mac in stations:
            subprocess.run(
                ["iw", "dev", WIFI_INTERFACE, "station", "del", mac],
                capture_output=True, timeout=2
            )
            print(f"[SystemManager] Deauthenticated WiFi STA: {mac}")
        print(f"[SystemManager] WiFi link DISCONNECTED")
    except Exception as e:
        print(f"[SystemManager] Error disconnecting WiFi: {e}")


def _derive_psk_hash(passphrase: str) -> str:
    return hashlib.sha256(passphrase.encode("utf-8")).hexdigest()


def _hostapd_cli_cmd(*args) -> bool:
    try:
        result = subprocess.run(
            ["sudo", "-n", HOSTAPD_CLI, "-i", HOSTAPD_IFNAME, "-p", HOSTAPD_CTRL_DIR, *args],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print(f"[SystemManager] hostapd_cli failed: {result.stderr.decode().strip()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("[SystemManager] hostapd_cli timeout")
        return False
    except Exception as e:
        print(f"[SystemManager] Failed to run hostapd_cli: {e}")
        return False


def send_to_sta(passphrase, timeout=10):
    """Send passphrase to STA, wait for ACK+PSK hash confirmation. Returns True on success."""
    expected_psk_hash = _derive_psk_hash(passphrase)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((STA_HOST, STA_PORT))
            s.sendall(passphrase.encode())
            print(f"[SystemManager] Sent passphrase to STA: {passphrase}")
            # Wait for STA acknowledgement
            ack = s.recv(128)
            if not ack:
                print(f"[SystemManager] Empty response from STA")
                return False
            ack = ack.decode("utf-8", errors="ignore").strip()
            if ack == "ACK":
                print("[SystemManager] ACK without PSK hash; reject rekey")
                return False
            if ack.startswith("ACK "):
                sta_psk_hash = ack[4:].strip()
                if sta_psk_hash == expected_psk_hash:
                    print("[SystemManager] PSK hash verified")
                    return True
                print("[SystemManager] PSK hash mismatch; reject rekey")
                return False
            if ack.startswith("NACK"):
                print(f"[SystemManager] STA reported PMK update failure")
                return False
            print(f"[SystemManager] Unexpected response from STA: {ack}")
            return False
    except socket.timeout:
        print(f"[SystemManager] Timeout waiting for STA ACK")
        return False
    except Exception as e:
        print(f"[SystemManager] Failed to send to STA: {e}")
        return False


def main():
    while True:
        # Fetch new passphrase, skip this rekey round on failure
        if not get_passphrase():
            print(f"[SystemManager] Skipping rekey - failed to get passphrase, DISCONNECTING WiFi")
            disconnect_wifi_link()
            time.sleep(REKEY_INTERVAL)
            continue
        # Wait for STA to confirm PMK update before triggering rekey
        if send_to_sta(latest_passphrase):
            # Flush AP PMKSA cache to avoid using stale PMK
            _hostapd_cli_cmd("pmksa_flush")
            # Give STA extra time for wpa_supplicant to fully prepare the new PMK
            # Note: this is an empirical delay, not a true confirmation mechanism
            # If still failing, try increasing to 1.0 or 2.0 seconds
            delay = 1.0
            time.sleep(delay)
            send_rekey()
            # Mark rekey triggered for ptk_receiver to monitor handshake result
            mark_rekey_triggered()
        else:
            print(f"[SystemManager] Skipping rekey - STA not ready, DISCONNECTING WiFi")
            disconnect_wifi_link()
        time.sleep(REKEY_INTERVAL)

if __name__ == "__main__":
    main()
