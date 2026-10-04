#!/usr/bin/env python3
"""Serve one local file to the WN3000RP BusyBox TFTP client."""

import argparse
import socket
import struct
from pathlib import Path

DEFAULT_HOST_IP = "192.168.157.236"
DEFAULT_DEVICE_IP = "192.168.157.22"
PORT = 1069


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("name")
    parser.add_argument("--host", default=DEFAULT_HOST_IP)
    parser.add_argument("--device", default=DEFAULT_DEVICE_IP)
    args = parser.parse_args()
    data = args.source.read_bytes()
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind((args.host, PORT))
    listener.settimeout(40)
    print(f"Serving {len(data)} bytes as {args.name} on {args.host}:{PORT}", flush=True)
    request, peer = listener.recvfrom(516)
    fields = request[2:].split(b"\0")
    if peer[0] != args.device or request[:2] != b"\0\1" or fields[0] != args.name.encode():
        raise ValueError(f"unexpected request from {peer}")
    listener.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, 0))
    sock.settimeout(5)
    block = 1
    offset = 0
    while True:
        chunk = data[offset : offset + 512]
        packet = struct.pack("!HH", 3, block) + chunk
        for _ in range(5):
            sock.sendto(packet, peer)
            try:
                ack, sender = sock.recvfrom(516)
            except socket.timeout:
                continue
            if sender[0] == args.device and ack == struct.pack("!HH", 4, block):
                peer = sender
                break
        else:
            raise TimeoutError(f"TFTP block {block} was not acknowledged")
        offset += len(chunk)
        if len(chunk) < 512:
            break
        block = (block + 1) & 0xFFFF
    sock.close()
    print(f"Sent {offset} bytes", flush=True)


if __name__ == "__main__":
    main()
