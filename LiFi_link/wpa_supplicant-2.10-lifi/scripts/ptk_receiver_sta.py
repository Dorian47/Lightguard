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

# WiFi interface name for checking association
WIFI_INTERFACE = os.environ.get("WIFI_INTERFACE", "wlx90de8088c693")
WIFI_INSTALL_WAIT = int(os.environ.get("WIFI_INSTALL_WAIT", "20"))

# Sync server settings (AP -> STA communication for PTK sync)
SYNC_HOST = "0.0.0.0"
SYNC_PORT = int(os.environ.get("STA_SYNC_PORT", "2223"))

# wifi link sender
WIFI_SEND_PTK_SCRIPT = Path(os.environ.get(
    "WIFI_SEND_PTK_SCRIPT",
    "/etc/system_manager_sta/send_ptk_sta.py",
))
WIFI_SEND_HOST = os.environ.get("WIFI_SEND_HOST", "127.0.0.1")
WIFI_SEND_PORT = os.environ.get("WIFI_SEND_PORT", "9900")

# Track last PTK to avoid duplicates
last_ptk_hex = None

# Pending PTK from LiFi (waiting for AP sync)
pending_ptk_hex = None
pending_ptk_lock = threading.Lock()

# Rekey watchdog settings
REKEY_TRIGGER_FILE_STA = os.environ.get("REKEY_TRIGGER_FILE_STA", "/tmp/rekey_triggered_sta")
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
    """Disconnect WiFi STA connection - protects WiFi link when LiFi handshake fails"""
    try:
        subprocess.run(
            ["iw", "dev", interface, "disconnect"],
            capture_output=True, timeout=2
        )
        print(f"[lifi-STA] WiFi link DISCONNECTED on {interface}")
    except Exception as e:
        print(f"[lifi-STA] Error disconnecting WiFi link: {e}")


def ptk_watchdog():
    """
    Monitor each rekey round:
    - Read the rekey_triggered_sta file written by get_csi_pmk.py
    - If rekey was triggered but no new PTK installed within HANDSHAKE_TIMEOUT, disconnect WiFi immediately
    """
    global watchdog_triggered
    last_handled_rekey = 0.0
    print(f"[lifi-STA] PTK watchdog started (handshake timeout: {HANDSHAKE_TIMEOUT}s)")
    while True:
        time.sleep(5)
        # Read rekey trigger timestamp
        try:
            with open(REKEY_TRIGGER_FILE_STA, "r") as f:
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
            print(f"[lifi-STA] WATCHDOG: PTK installed after rekey, all good")
        else:
            print(f"[lifi-STA] WATCHDOG: No PTK installed within {HANDSHAKE_TIMEOUT}s after rekey trigger")
            print(f"[lifi-STA] WATCHDOG: LiFi handshake failed, DISCONNECTING WiFi")
            disconnect_wifi_link(WIFI_INTERFACE)


def check_wifi_associated(interface: str) -> bool:
    """Check if WiFi STA is associated"""
    try:
        result = subprocess.run(
            ["iw", interface, "link"],
            capture_output=True,
            timeout=2
        )
        return b"Connected to" in result.stdout
    except Exception:
        return False


def wait_for_wifi_association(interface: str, timeout: int = 10) -> bool:
    """Wait for WiFi STA to associate"""
    print(f"[lifi-STA] Waiting for WiFi to associate on {interface}...")
    for i in range(timeout):
        if check_wifi_associated(interface):
            print(f"[lifi-STA] WiFi associated")
            return True
        time.sleep(1)
    print(f"[lifi-STA] Timeout waiting for WiFi association")
    return False


def send_ptk_to_wifi(ptk_hex: str) -> bool:
    """Send PTK to WiFi STA. Returns True on success."""
    if not WIFI_SEND_PTK_SCRIPT.exists():
        print(f"[lifi-STA] WiFi sender not found: {WIFI_SEND_PTK_SCRIPT}")
        return False
    cmd = [sys.executable, str(WIFI_SEND_PTK_SCRIPT), ptk_hex]
    if WIFI_SEND_HOST:
        cmd += ["--host", WIFI_SEND_HOST]
    if WIFI_SEND_PORT:
        cmd += ["--port", str(WIFI_SEND_PORT)]
    try:
        subprocess.run(cmd, check=True, timeout=5)
        print("[lifi-STA] PTK forwarded to WiFi STA")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[lifi-STA] Failed to forward PTK to WiFi STA: {exc}")
        return False
    except subprocess.TimeoutExpired:
        print(f"[lifi-STA] Timeout forwarding PTK to WiFi STA")
        return False


def run_sync_server():
    """
    Sync server (similar to WiFi_link sta_ptk_sync.py):
    1. Receive SYNC <ptk_hex> (sent by AP via LiFi link)
    2. Use AP's PTK directly (ensures consistency)
    3. Verify WiFi is associated
    4. Reply READY
    5. Wait for INSTALL
    6. STA installs PTK to WiFi first
    7. Reply OK (tells AP it can install now)
    
    Key: STA installs first, replies OK, then AP installs
    """
    global pending_ptk_hex, last_ptk_hex, last_ptk_install_time, watchdog_triggered
    
    sync_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sync_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sync_server.bind((SYNC_HOST, SYNC_PORT))
    sync_server.listen(5)
    print(f"[lifi-STA] Sync server listening on {SYNC_HOST}:{SYNC_PORT}")
    
    while True:
        conn = None
        try:
            conn, addr = sync_server.accept()
            conn.settimeout(15)  # Increased timeout
            
            # Step 1: Receive SYNC message
            data = conn.recv(256).decode().strip()
            if not data.startswith("SYNC "):
                print(f"[lifi-STA] Invalid sync message: {data}")
                conn.close()
                continue
            
            ap_ptk_hex = data[5:].strip()
            print(f"[lifi-STA] Received SYNC from AP (LiFi link): {ap_ptk_hex[:32]}...")
            
            # Step 2: Use AP's PTK directly (not relying on local pending)
            # This ensures both sides have the same PTK
            with pending_ptk_lock:
                pending_ptk_hex = ap_ptk_hex
                print(f"[lifi-STA] Using AP's PTK for sync")
            
            # Step 3: Ensure WiFi is associated
            if not check_wifi_associated(WIFI_INTERFACE):
                print(f"[lifi-STA] WiFi not associated yet, waiting...")
                wait_for_wifi_association(WIFI_INTERFACE, timeout=WIFI_INSTALL_WAIT)
            if not check_wifi_associated(WIFI_INTERFACE):
                print(f"[lifi-STA] WiFi still not associated, sending NOTREADY")
                conn.sendall(b"NOTREADY\n")
                conn.close()
                continue

            # Step 4: Reply READY (LiFi link is up, ready to install)
            conn.sendall(b"READY\n")
            print(f"[lifi-STA] Sent READY to AP")
            
            # Step 5: Wait for INSTALL command
            install_cmd = conn.recv(64).decode().strip()
            if install_cmd != "INSTALL":
                print(f"[lifi-STA] Unexpected command: {install_cmd}")
                conn.sendall(b"FAIL\n")
                disconnect_wifi_link(WIFI_INTERFACE)
                conn.close()
                continue
            
            print(f"[lifi-STA] Received INSTALL from AP")
            
            # Step 6: STA installs PTK to WiFi first
            with pending_ptk_lock:
                if pending_ptk_hex and check_wifi_associated(WIFI_INTERFACE):
                    ok = send_ptk_to_wifi(pending_ptk_hex)
                    if ok:
                        last_ptk_hex = pending_ptk_hex
                        pending_ptk_hex = None
                        # Update watchdog timer
                        with ptk_install_lock:
                            last_ptk_install_time = time.time()
                            watchdog_triggered = False
                        # Step 7: Reply OK, tell AP it can install now
                        conn.sendall(b"OK\n")
                        print(f"[lifi-STA] PTK installed to WiFi, sent OK to AP")
                    else:
                        conn.sendall(b"FAIL\n")
                        print(f"[lifi-STA] Failed to install PTK to WiFi, disconnecting WiFi")
                        disconnect_wifi_link(WIFI_INTERFACE)
                else:
                    conn.sendall(b"NOTREADY\n")
                    print(f"[lifi-STA] WiFi not associated or no PTK, disconnecting WiFi")
                    disconnect_wifi_link(WIFI_INTERFACE)
            
        except socket.timeout:
            print(f"[lifi-STA] Sync connection timeout, disconnecting WiFi")
            disconnect_wifi_link(WIFI_INTERFACE)
        except Exception as e:
            print(f"[lifi-STA] Sync server error: {e}, disconnecting WiFi")
            disconnect_wifi_link(WIFI_INTERFACE)
        finally:
            if conn:
                conn.close()

# Start sync server thread
sync_thread = threading.Thread(target=run_sync_server, daemon=True)
sync_thread.start()

# Start PTK watchdog thread
watchdog_thread = threading.Thread(target=ptk_watchdog, daemon=True)
watchdog_thread.start()

while True:
    conn = None
    try:
        conn, addr = s.accept()
        data = conn.recv(PTK_LEN)
        if not data:
            print("[lifi-STA] Received empty data, skipping")
            continue
        if len(data) != PTK_LEN:
            print(f"[lifi-STA] Invalid PTK length: got {len(data)}, expected {PTK_LEN}")
            continue
        ptk_hex = binascii.hexlify(data).decode()
        
        # Dedup: skip duplicate PTK
        if ptk_hex == last_ptk_hex:
            print(f"[lifi-STA] Duplicate PTK, skipping")
            continue
        
        print(f"[lifi-STA] PTK from LiFi: {ptk_hex}")
        tk = data[-16:]
        write_ptk_tk("/tmp/sta_ptk.bin", tk)
        
        # Store as pending, wait for AP sync command
        with pending_ptk_lock:
            pending_ptk_hex = ptk_hex
        print("[lifi-STA] PTK saved, waiting for AP sync...")
        
    except Exception as e:
        print(f"[lifi-STA] Error: {e}")
    finally:
        if conn:
            conn.close()
