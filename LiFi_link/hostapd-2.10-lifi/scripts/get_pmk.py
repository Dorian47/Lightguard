import socket
import os
import random

CSI_LEN = 8
PORT = 9911

def get_csi():
    #wait til later
    return b"00000000"


def csi_to_pass(csi):
    #wait til later
    print(csi)
    return csi[:8]

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('127.0.0.1', PORT))
server.listen(1)

print(f"[Random Key] Listening on port {PORT}...")

try:
    while True:
        conn, addr = server.accept()
        print(f"[Random Key] Connection from {addr}")
        csi = get_csi()

        pswd = csi_to_pass(csi)
        print(f"[Random Key] generating pmk {pswd}")
        conn.sendall(pswd)
        conn.close()
except KeyboardInterrupt:
    print("\n[Random Key] Shutting down.")