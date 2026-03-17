import socket
import argparse
import subprocess
import time


EXAMPLE_PTK_HEX = (
    "00112233445566778899aabbccddeeff"
    "0102030405060708090a0b0c0d0e0f10"
    "aabbccddeeff00112233445566778899"
)

# WiFi interface name, configurable via environment variable
import os
WIFI_INTERFACE = os.environ.get("WIFI_INTERFACE", "wlx90de8088c693")


def check_wifi_associated(interface: str) -> bool:
    """Check if the WiFi interface is associated"""
    try:
        result = subprocess.run(
            ["iw", interface, "link"],
            capture_output=True,
            timeout=2
        )
        # "Connected to" indicates association
        return b"Connected to" in result.stdout
    except Exception:
        return False


def wait_for_association(interface: str, timeout: int = 10) -> bool:
    """Wait for WiFi interface to associate"""
    print(f"[send_ptk_sta] Waiting for {interface} to associate...")
    for i in range(timeout):
        if check_wifi_associated(interface):
            print(f"[send_ptk_sta] {interface} is associated")
            return True
        time.sleep(1)
    print(f"[send_ptk_sta] Timeout waiting for {interface} association")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send custom PTK to wpa_supplicant via local TCP socket.")
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
    parser.add_argument("--port", type=int, default=9900)
    parser.add_argument("--prefix", action="store_true",
                        help="Prefix with 'PTK ' before sending")
    parser.add_argument("--interface", default=WIFI_INTERFACE,
                        help="WiFi interface to check association")
    parser.add_argument("--wait-timeout", type=int, default=10,
                        help="Timeout for waiting WiFi association")
    parser.add_argument("--retry", type=int, default=3,
                        help="Number of retries if send fails")
    args = parser.parse_args()

    # Wait for WiFi association
    if not wait_for_association(args.interface, args.wait_timeout):
        print(f"[send_ptk_sta] WiFi not associated, PTK may fail to install")
        # Continue anyway, let wpa_supplicant decide whether to reject

    payload = args.ptk_hex.strip()
    if args.prefix:
        payload = "PTK " + payload

    # Retry mechanism
    for attempt in range(args.retry):
        try:
            with socket.create_connection((args.host, args.port), timeout=2) as sock:
                sock.sendall((payload + "\n").encode())
            print(f"[send_ptk_sta] sent to STA {args.host}:{args.port}")
            return
        except Exception as e:
            print(f"[send_ptk_sta] attempt {attempt+1}/{args.retry} failed: {e}")
            if attempt < args.retry - 1:
                time.sleep(1)
    
    print(f"[send_ptk_sta] Failed to send PTK after {args.retry} attempts")


if __name__ == "__main__":
    main()
