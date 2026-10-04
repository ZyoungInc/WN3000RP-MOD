#!/usr/bin/env python3
"""Receive one read-only MTD dump from WN3000RP via TFTP WRQ."""

import argparse
import os
import socket
import struct
from pathlib import Path

SOURCE_IP = "192.168.157.22"
HOST_IP = "192.168.157.236"
PORT = 1069
MAX_BYTES = 4 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=["mtd1-linux.bin", "mtd2-rootfs.bin"])
    args = parser.parse_args()
    name = args.name
    dest = Path(__file__).resolve().parents[1] / "firmware" / "original" / name
    os.umask(0o077)
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.bind((HOST_IP, PORT))
    listener.settimeout(30)
    print(f"Waiting for {SOURCE_IP} TFTP WRQ on {HOST_IP}:{PORT}", flush=True)
    request, peer = listener.recvfrom(516)
    parts = request[2:].split(b"\0")
    if peer[0] != SOURCE_IP or request[:2] != b"\0\2" or not parts or parts[0] != name.encode():
        raise ValueError(f"unexpected request from {peer}")
    listener.close()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST_IP, 0))
    sock.settimeout(5)
    block = 0
    size = 0
    try:
        with dest.open("xb") as out:
            sock.sendto(struct.pack("!HH", 4, 0), peer)
            while True:
                data, sender = sock.recvfrom(516)
                if sender[0] != SOURCE_IP or len(data) < 4 or data[:2] != b"\0\3":
                    continue
                number = struct.unpack("!H", data[2:4])[0]
                if number == (block + 1) & 0xFFFF:
                    out.write(data[4:])
                    size += len(data) - 4
                    if size > MAX_BYTES:
                        raise ValueError("transfer exceeds expected MTD partition")
                    block = number
                    sock.sendto(struct.pack("!HH", 4, block), sender)
                    if len(data) < 516:
                        break
                elif number == block:
                    sock.sendto(struct.pack("!HH", 4, block), sender)
    finally:
        sock.close()
    print(f"Received {size} bytes in {block} blocks: {dest}", flush=True)


if __name__ == "__main__":
    main()
