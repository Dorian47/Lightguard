import os
import time
import socket
import binascii
import tempfile
import subprocess
import sys
import threading
from pathlib import Path

PTK_HOST = '127.0.0.1'
PTK_PORT = 8877
PTK_LEN = 48

# WiFi interface name for checking STA connection
WIFI_INTERFACE = os.environ.get("WIFI_INTERFACE", "wlx90de8088c692")

# STA sync settings (AP -> STA communication for PTK sync)
STA_SYNC_HOST = os.environ.get("STA_SYNC_HOST", "192.168.2.131")
STA_SYNC_PORT = int(os.environ.get("STA_SYNC_PORT", "2223"))

# wifi link sender
WIFI_SEND_PTK_SCRIPT = Path(os.environ.get(
    "WIFI_SEND_PTK_SCRIPT",
    "/etc/system_manager_ap/send_ptk_ap.py",
))
WIFI_SEND_HOST = os.environ.get("WIFI_SEND_HOST", "127.0.0.1")
WIFI_SEND_PORT = os.environ.get("WIFI_SEND_PORT", "9899")

# Track last PTK to avoid duplicates
last_ptk_hex = None

# Rekey watchdog settings
REKEY_TRIGGER_FILE = os.environ.get("REKEY_TRIGGER_FILE", "/tmp/rekey_triggered")
HANDSHAKE_TIMEOUT = int(os.environ.get("HANDSHAKE_TIMEOUT", "30"))

# Watchdog state: track last successful PTK install
last_ptk_install_time = time.time()
ptk_install_lock = threading.Lock()
watchdog_triggered = False


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((PTK_HOST, PTK_PORT))
s.listen(5)
print(f"Listening on {PTK_HOST}:{PTK_PORT} (expecting {PTK_LEN} bytes)")

def write_ptk_tk(path, ptk_tk: bytes):
    directory = os.path.dirname(path)
    fd, tempath = tempfile.mkstemp(prefix="ptk_", dir=directory)
    with os.fdopen(fd, "wb") as f:
        f.write(ptk_tk)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tempath,path)


def disconnect_wifi_link(interface: str):
    """Disconnect WiFi link - deauthenticate all STAs from WiFi AP (protects WiFi when LiFi handshake fails)"""
    try:
        result = subprocess.run(
            ["iw", "dev", interface, "station", "dump"],
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
            print(f"[lifi-AP] No WiFi STAs connected to disconnect")
            return
        for mac in stations:
            subprocess.run(
                ["iw", "dev", interface, "station", "del", mac],
                capture_output=True, timeout=2
            )
            print(f"[lifi-AP] Deauthenticated WiFi STA: {mac}")
        print(f"[lifi-AP] WiFi link DISCONNECTED ({len(stations)} STAs removed)")
    except Exception as e:
        print(f"[lifi-AP] Error disconnecting WiFi link: {e}")


def ptk_watchdog():
    """
    Monitor each rekey round:
    - Read the rekey_triggered file written by system_manager.py
    - If rekey was triggered but no new PTK installed within HANDSHAKE_TIMEOUT, disconnect WiFi immediately
    """
    global watchdog_triggered
    last_handled_rekey = 0.0
    print(f"[lifi-AP] PTK watchdog started (handshake timeout: {HANDSHAKE_TIMEOUT}s)")
    while True:
        time.sleep(5)
        # Read rekey trigger timestamp
        try:
            with open(REKEY_TRIGGER_FILE, "r") as f:
                rekey_time = float(f.read().strip())
        except (FileNotFoundError, ValueError):
            continue
        # Skip already-handled triggers
        if rekey_time <= last_handled_rekey:
            continue
        # Wait until HANDSHAKE_TIMEOUT has elapsed before checking
        elapsed = time.time() - rekey_time
        if elapsed < HANDSHAKE_TIMEOUT:
            continue
        # Check if PTK was installed after this rekey trigger
        with ptk_install_lock:
            ptk_time = last_ptk_install_time
        last_handled_rekey = rekey_time
        if ptk_time >= rekey_time:
            print(f"[lifi-AP] WATCHDOG: PTK installed after rekey, all good")
        else:
            print(f"[lifi-AP] WATCHDOG: No PTK installed within {HANDSHAKE_TIMEOUT}s after rekey trigger")
            print(f"[lifi-AP] WATCHDOG: LiFi handshake failed, DISCONNECTING WiFi")
            disconnect_wifi_link(WIFI_INTERFACE)


def check_wifi_sta_connected(interface: str) -> bool:
    """Check if any STAs are connected to the WiFi AP"""
    try:
        result = subprocess.run(
            ["iw", interface, "station", "dump"],
            capture_output=True,
            timeout=2
        )
        return len(result.stdout.strip()) > 0
    except Exception:
        return False


def wait_for_wifi_sta(interface: str, timeout: int = 10) -> bool:
    """Wait for a WiFi STA to connect"""
    print(f"[lifi-AP] Waiting for WiFi STA to connect to {interface}...")
    for i in range(timeout):
        if check_wifi_sta_connected(interface):
            print(f"[lifi-AP] WiFi STA connected")
            return True
        time.sleep(1)
    print(f"[lifi-AP] Timeout waiting for WiFi STA")
    return False


def send_ptk_to_wifi(ptk_hex: str) -> bool:
    """Send PTK to WiFi AP. Returns True on success."""
    if not WIFI_SEND_PTK_SCRIPT.exists():
        print(f"[lifi-AP] WiFi sender not found: {WIFI_SEND_PTK_SCRIPT}")
        return False
    cmd = [sys.executable, str(WIFI_SEND_PTK_SCRIPT), ptk_hex]
    if WIFI_SEND_HOST:
        cmd += ["--host", WIFI_SEND_HOST]
    if WIFI_SEND_PORT:
        cmd += ["--port", str(WIFI_SEND_PORT)]
    try:
        subprocess.run(cmd, check=True, timeout=5)
        print("[lifi-AP] PTK forwarded to WiFi AP")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[lifi-AP] Failed to forward PTK to WiFi AP: {exc}")
        return False
    except subprocess.TimeoutExpired:
        print(f"[lifi-AP] Timeout forwarding PTK to WiFi AP")
        return False


def sync_with_sta_and_install(ptk_hex: str) -> bool:
    """
    Sync mechanism (similar to WiFi_link ap_ptk_sync.py):
    1. Send SYNC <ptk_hex> to STA (via LiFi link)
    2. Wait for STA to reply READY (confirms LiFi link is up)
    3. Check if WiFi STA is connected
    4. Send INSTALL to STA
    5. Wait for STA to reply OK (STA has installed PTK to WiFi)
    6. AP installs PTK to WiFi
    
    Key: STA installs first, AP installs after confirmation to ensure sync
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(15)  # Increased timeout
            sock.connect((STA_SYNC_HOST, STA_SYNC_PORT))
            
            # Step 1: Send SYNC message (PTK hex)
            sync_msg = f"SYNC {ptk_hex}\n"
            sock.sendall(sync_msg.encode())
            print(f"[lifi-AP] Sent SYNC to STA via LiFi link")
            
            # Step 2: Wait for READY reply (confirms LiFi link is up, STA is ready)
            response = sock.recv(64).decode().strip()
            if response != "READY":
                print(f"[lifi-AP] STA not ready: {response}")
                return False
            print(f"[lifi-AP] Received READY from STA (LiFi link OK)")
            
            # Step 3: Check if WiFi STA is connected
            if not check_wifi_sta_connected(WIFI_INTERFACE):
                print(f"[lifi-AP] WiFi STA not connected, waiting...")
                wait_for_wifi_sta(WIFI_INTERFACE, timeout=10)
            
            # Step 4: Send INSTALL signal
            sock.sendall(b"INSTALL\n")
            print(f"[lifi-AP] Sent INSTALL to STA")
            
            # Step 5: Wait for STA install confirmation (critical!)
            reply = sock.recv(64).decode().strip()
            if reply != "OK":
                print(f"[lifi-AP] STA install failed: {reply}")
                return False
            print(f"[lifi-AP] STA installed PTK to WiFi successfully")
            
            # Step 6: AP installs PTK to WiFi (STA installed first)
            send_ptk_to_wifi(ptk_hex)
            print(f"[lifi-AP] AP installed PTK to WiFi")
            
            return True
            
    except socket.timeout:
        print(f"[lifi-AP] Timeout syncing with STA")
        return False
    except ConnectionRefusedError:
        print(f"[lifi-AP] STA sync service not available")
        return False
    except Exception as e:
        print(f"[lifi-AP] Error syncing with STA: {e}")
        return False


# Start PTK watchdog thread
watchdog_thread = threading.Thread(target=ptk_watchdog, daemon=True)
watchdog_thread.start()

while True:
    conn = None
    try:
        conn, addr = s.accept()
        data = conn.recv(PTK_LEN)
        if not data:
            print("[lifi-AP] Received empty data, skipping")
            continue
        if len(data) != PTK_LEN:
            print(f"[lifi-AP] Invalid PTK length: got {len(data)}, expected {PTK_LEN}")
            continue
        ptk_hex = binascii.hexlify(data).decode()
        
        # Dedup: skip duplicate PTK
        if ptk_hex == last_ptk_hex:
            print(f"[lifi-AP] Duplicate PTK, skipping")
            continue
        last_ptk_hex = ptk_hex
        
        print(f"[lifi-AP] PTK: {ptk_hex}")
        tk = data[-16:]
        write_ptk_tk("/tmp/ap_ptk.bin", tk)
        
        # Use sync mechanism to install PTK
        if sync_with_sta_and_install(ptk_hex):
            # Success: update watchdog timer
            with ptk_install_lock:
                last_ptk_install_time = time.time()
                watchdog_triggered = False
            print("[lifi-AP] PTK synced and installed!")
        else:
            # Sync failed: disconnect WiFi to prevent stale PTK usage
            print("[lifi-AP] Sync failed, DISCONNECTING WiFi to prevent stale PTK usage")
            disconnect_wifi_link(WIFI_INTERFACE)
            
    except Exception as e:
        print(f"[lifi-AP] Error: {e}")
    finally:
        if conn:
            conn.close()
