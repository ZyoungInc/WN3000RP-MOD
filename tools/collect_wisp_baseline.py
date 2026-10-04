#!/usr/bin/env python3
"""Capture the live WISP baseline without changing device configuration."""

import datetime
import os
from pathlib import Path

import pexpect

ROOT = Path(__file__).resolve().parents[1]
HOST = "192.168.157.22"
GROUPS = {
    "wisp-before.txt": [
        "nvram show", "ifconfig -a", "route -n", "brctl show",
        "cat /proc/net/dev", "cat /proc/sys/net/ipv4/ip_forward", "ps",
        "wl status", "wl assoc", "wl bssid", "wl ssid", "wl mode",
        "wl ap", "wl wet", "wl wds", "wl dump",
        "wl chanspec", "wl channel", "wl rate", "wl nrate",
    ],
    "wisp-nat-live.txt": [
        "cat /proc/net/ip_tables_names", "cat /proc/net/ip_tables_matches",
        "cat /proc/net/ip_tables_targets",
        "cat /proc/net/nf_conntrack 2>/dev/null",
        "cat /proc/net/ip_conntrack 2>/dev/null", "lsmod",
        "cat /proc/modules", "find /lib/modules -type f",
        "find /proc -iname '*nat*' -o -iname '*conntrack*'",
        "ls -la /tmp /var /tmp/var", "cat /tmp/udhcpd.conf",
    ],
}


def main():
    os.umask(0o077)
    shell = pexpect.spawn("telnet", [HOST], encoding="latin-1", timeout=35,
                          maxread=131072)
    shell.expect(r"\r?\n# ")
    for filename, commands in GROUPS.items():
        path = ROOT / "logs" / filename
        with path.open("w", encoding="latin-1") as log:
            log.write(f"Collected {datetime.datetime.now().astimezone().isoformat()}\n")
            log.write("Raw output may contain credentials; keep this file private.\n")
            for command in commands:
                shell.sendline(command)
                try:
                    shell.expect(r"\r?\n# ", timeout=40)
                except pexpect.TIMEOUT:
                    log.write(f"\n===== {command} =====\n{shell.before}\n[TIMEOUT]\n")
                    raise
                log.write(f"\n===== {command} =====\n{shell.before}")
        print(f"Saved {len(commands)} sections to {path}")
    shell.sendline("exit")
    shell.close(force=True)


if __name__ == "__main__":
    main()
