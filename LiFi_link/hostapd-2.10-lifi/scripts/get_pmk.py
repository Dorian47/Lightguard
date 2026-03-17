import socket
import os
import random

PASSPHRASE_LEN = 8
PORT = 9911

def generate_passphrase():
    return b"00000000"


def passphrase_to_bytes(raw):
    print(raw)
    return raw[:8]

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('127.0.0.1', PORT))
server.listen(1)

print(f"[Random Key] Listening on port {PORT}...")

try:
    while True:
        conn, addr = server.accept()
        print(f"[Random Key] Connection from {addr}")
        raw = generate_passphrase()

        pswd = passphrase_to_bytes(raw)
        print(f"[Random Key] generating pmk {pswd}")
        conn.sendall(pswd)
        conn.close()
except KeyboardInterrupt:
    print("\n[Random Key] Shutting down.")