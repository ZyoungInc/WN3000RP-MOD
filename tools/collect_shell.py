#!/usr/bin/env python3
"""Collect read-only diagnostics over the device's temporary Telnet shell."""

import datetime
import os
from pathlib import Path

import pexpect


HOST = "192.168.157.22"
OUT = Path(__file__).resolve().parents[1] / "logs" / "shell-info.txt"
COMMANDS = [
    "uname -a", "cat /proc/version", "cat /proc/cpuinfo", "cat /proc/meminfo",
    "cat /proc/mtd", "cat /proc/partitions", "mount", "df -h", "free",
    "ps", "busybox", "cat /etc/passwd", "cat /etc/group",
    "cat /etc/inittab", "cat /etc/profile", "ls -la /",
    "ls -la /bin /sbin /usr/bin /usr/sbin", "ls -la /etc",
    "ls -la /lib /lib/modules", "ifconfig -a", "route -n", "brctl show",
    "cat /proc/net/dev", "nvram show 2>/dev/null", "wl ver 2>/dev/null",
    "wl cap 2>/dev/null", "wl status 2>/dev/null", "wl dump 2>/dev/null",
]


def main():
    os.umask(0o077)
    child = pexpect.spawn("telnet", [HOST], encoding="latin-1", timeout=30,
                          maxread=65536)
    child.expect(r"\r?\n# ")
    with OUT.open("w", encoding="latin-1") as log:
        log.write(f"Collected: {datetime.datetime.now().astimezone().isoformat()}\n")
        log.write("WARNING: raw NVRAM and status output may contain credentials; keep this file private.\n")
        for command in COMMANDS:
            log.write(f"\n===== {command} =====\n")
            child.sendline(command)
            try:
                child.expect(r"\r?\n# ", timeout=35)
                log.write(child.before)
            except pexpect.TIMEOUT:
                log.write(child.before)
                log.write("\n[timeout waiting for shell prompt]\n")
                break
    child.sendline("exit")
    child.close(force=True)
    print(f"Saved {len(COMMANDS)} command sections to {OUT}")


if __name__ == "__main__":
    main()
