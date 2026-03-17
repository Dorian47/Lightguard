import socket
import argparse
import subprocess
import time
import os


EXAMPLE_PTK_HEX = (
    "00112233445566778899aabbccddeeff"
    "0102030405060708090a0b0c0d0e0f10"
    "aabbccddeeff00112233445566778899"
)

# WiFi interface name, configurable via environment variable
WIFI_INTERFACE = os.environ.get("WIFI_INTERFACE", "wlx90de8088c692")


def check_sta_connected(interface: str) -> bool:
    """Check if any STAs are connected to hostapd"""
    try:
        # Use iw to check station list
        result = subprocess.run(
            ["iw", interface, "station", "dump"],
            capture_output=True,
            timeout=2
        )
        # Non-empty output means at least one STA is connected
        return len(result.stdout.strip()) > 0
    except Exception:
        return False


def wait_for_sta_connected(interface: str, timeout: int = 10) -> bool:
    """Wait for a STA to connect to the AP"""
    print(f"[send_ptk_ap] Waiting for STA to connect to {interface}...")
    for i in range(timeout):
        if check_sta_connected(interface):
            print(f"[send_ptk_ap] STA connected to {interface}")
            return True
        time.sleep(1)
    print(f"[send_ptk_ap] Timeout waiting for STA connection")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send custom PTK to hostapd via local TCP socket.")
    parser.add_argument(
        "ptk_hex",
        nargs="?",
        default=EXAMPLE_PTK_HEX,
        help=(
            "PTK hex string (KCK[16] + KEK[16] + TK[tk_len]). "
            "For CCMP tk_len=16 => 96 hex chars. "
            "If omitted, a built-in example is used."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9899)
    parser.add_argument("--prefix", action="store_true",
                        help="Prefix with 'PTK ' before sending")
    parser.add_argument("--interface", default=WIFI_INTERFACE,
                        help="WiFi interface to check STA connection")
    parser.add_argument("--wait-timeout", type=int, default=10,
                        help="Timeout for waiting STA connection")
    parser.add_argument("--retry", type=int, default=3,
                        help="Number of retries if send fails")
    args = parser.parse_args()

    # Wait for STA to connect
    if not wait_for_sta_connected(args.interface, args.wait_timeout):
        print(f"[send_ptk_ap] No STA connected, PTK may fail to install")

    payload = args.ptk_hex.strip()
    if args.prefix:
        payload = "PTK " + payload

    # Retry mechanism
    for attempt in range(args.retry):
        try:
            with socket.create_connection((args.host, args.port), timeout=2) as sock:
                sock.sendall((payload + "\n").encode())
            print(f"[send_ptk_ap] sent to AP {args.host}:{args.port}")
            return
        except Exception as e:
            print(f"[send_ptk_ap] attempt {attempt+1}/{args.retry} failed: {e}")
            if attempt < args.retry - 1:
                time.sleep(1)
    
    print(f"[send_ptk_ap] Failed to send PTK after {args.retry} attempts")


if __name__ == "__main__":
    main()
