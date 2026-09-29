"""SSH ProxyCommand for the user's optional LAN HTTP proxy (no credentials)."""

import argparse
import select
import socket
import sys

parser = argparse.ArgumentParser()
parser.add_argument("proxy_host")
parser.add_argument("proxy_port", type=int)
parser.add_argument("host")
parser.add_argument("port", type=int)
args = parser.parse_args()
sock = socket.create_connection((args.proxy_host, args.proxy_port), 10)
target = f"{args.host}:{args.port}"
sock.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
header = bytearray()
while not header.endswith(b"\r\n\r\n") and len(header) < 16384:
    chunk = sock.recv(1)
    if not chunk:
        raise SystemExit("HTTP proxy closed the connection")
    header.extend(chunk)
if not header.split(b"\r\n", 1)[0].startswith((b"HTTP/1.1 200", b"HTTP/1.0 200")):
    raise SystemExit("HTTP proxy refused CONNECT")
sock.settimeout(None)
while True:
    ready, _, _ = select.select([sock, sys.stdin.buffer], [], [])
    if sock in ready:
        chunk = sock.recv(65536)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
    if sys.stdin.buffer in ready:
        chunk = sys.stdin.buffer.read1(65536)
        if not chunk:
            break
        sock.sendall(chunk)
