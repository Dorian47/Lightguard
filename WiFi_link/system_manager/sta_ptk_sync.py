import argparse
import os
import socket

LOCAL_PTK_HOST = "127.0.0.1"
LOCAL_PTK_PORT = 9900


def forward_to_local(payload: str) -> bool:
    try:
        with socket.create_connection((LOCAL_PTK_HOST, LOCAL_PTK_PORT), timeout=3) as sock:
            sock.sendall((payload + "\n").encode())
        return True
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="STA-side PTK bridge: receive PTK over TCP and forward to local listener."
    )
    parser.add_argument("--listen", default=os.environ.get("STA_BRIDGE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=10000)
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.listen, args.port))
    server.listen(5)

    print(f"STA bridge listening on {args.listen}:{args.port}")

    while True:
        client, _ = server.accept()
        with client:
            data = client.recv(4096)
            if not data:
                continue
            payload = data.decode(errors="ignore").strip()
            ok = forward_to_local(payload)
            client.sendall(b"OK" if ok else b"FAIL")


if __name__ == "__main__":
    main()
