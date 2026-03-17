import argparse
import os
import socket

EXAMPLE_PTK_HEX = (
    "00112233445566778899aabbccddeeff"
    "0102030405060708090a0b0c0d0e0f10"
    "aabbccddeeff00112233445566778899"
)


def send_payload(host: str, port: int, payload: str, expect_reply: bool = False) -> str:
    with socket.create_connection((host, port), timeout=3) as sock:
        sock.sendall((payload + "\n").encode())
        if not expect_reply:
            return ""
        sock.shutdown(socket.SHUT_WR)
        data = sock.recv(1024)
        return data.decode(errors="ignore").strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AP-side PTK sync: send PTK to STA bridge, then update AP locally."
    )
    parser.add_argument("ptk_hex", nargs="?", default=EXAMPLE_PTK_HEX)
    parser.add_argument("--sta-host", default=os.environ.get("STA_BRIDGE_HOST", "192.168.1.151"))
    parser.add_argument("--sta-port", type=int, default=10000)
    parser.add_argument("--ap-host", default="127.0.0.1")
    parser.add_argument("--ap-port", type=int, default=9899)
    parser.add_argument("--prefix", action="store_true")
    args = parser.parse_args()

    payload = args.ptk_hex.strip()
    if args.prefix:
        payload = "PTK " + payload

    reply = send_payload(args.sta_host, args.sta_port, payload, expect_reply=True)
    if reply != "OK":
        raise SystemExit(f"STA bridge failed: {reply or 'no reply'}")

    send_payload(args.ap_host, args.ap_port, payload)
    print("PTK sync done (STA OK, AP updated)")


if __name__ == "__main__":
    main()
