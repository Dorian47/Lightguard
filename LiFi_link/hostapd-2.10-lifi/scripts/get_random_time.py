import socket
import os
import random
import time

PASSPHRASE_LEN = 8
PORT = 9911


def get_from_time():
    key = []
    for i in range(8):
        start = time.perf_counter_ns()
        _ = [j*j for j in range(10000)]
        end = time.perf_counter_ns()
        #print(end)
        digit = end%10
        key.append(digit)
    password = ''.join(str(d) for d in key)
    return password



def generate_passphrase():
    pswd = get_from_time()
    b = bytearray()
    b.extend(map(ord, pswd))
    return b


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