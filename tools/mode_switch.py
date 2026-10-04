#!/usr/bin/env python3
"""Switch the owner's WN3000RP v1 between tested RAM-only network modes.

Requires pexpect, cryptography, telnet, NetworkManager (only for --share-computer).
No nvram set/commit, MTD write, or firmware update. Device reboot restores PSR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import ipaddress
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pexpect

from telnetenable_udp import packet


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
LOGS = ROOT / "logs"
PSR_IP = "192.168.157.22"
WISP_IP = "192.168.50.1"
AP_IP = "10.42.57.2"
DEVICE_MAC = "20:E5:2A:02:15:D0"
TEST_GATEWAY = "192.168.157.245"
ORIGINAL_GATEWAY_MAC = bytes.fromhex("0a3c63864d9f")
SHARE_NAME = "WN3000RP-ap-script"
SHELL_PROMPT = r"\r?\n# "


class SwitchError(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def run_local(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, text=True, capture_output=True, timeout=30)
    if check and result.returncode:
        raise SwitchError(f"{' '.join(argv)}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def tcp_open(ip: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def route_to(ip: str) -> tuple[str, str]:
    output = run_local(["ip", "-4", "route", "get", ip]).stdout
    dev = re.search(r"\bdev (\S+)", output)
    src = re.search(r"\bsrc (\d+\.\d+\.\d+\.\d+)", output)
    if not dev or not src:
        raise SwitchError("无法判定电脑到设备的接口和源地址")
    return dev.group(1), src.group(1)


def wait_port(ip: str, port: int, seconds: int = 10) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if tcp_open(ip, port, .7):
            return True
        time.sleep(.4)
    return False


def enable_telnet(ip: str, username: str) -> None:
    if tcp_open(ip, 23):
        return
    password = getpass.getpass(f"{ip} 原厂 Web 管理密码（不保存）：")
    if not password:
        raise SwitchError("密码为空，已取消")
    data = packet(DEVICE_MAC, username, password)
    del password
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, (ip, 23))
    if not wait_port(ip, 23, 8):
        raise SwitchError("TelnetEnable 未打开端口 23；请检查管理密码，或断电重启设备后再试")


class Shell:
    def __init__(self, ip: str):
        self.child = pexpect.spawn("telnet", [ip], encoding="latin-1", timeout=12)
        self.child.expect(SHELL_PROMPT)

    def command(self, cmd: str, timeout: int = 12) -> str:
        self.child.sendline(cmd)
        self.child.expect(SHELL_PROMPT, timeout=timeout)
        return self.child.before.replace("\r", "")

    def send_disruptive(self, cmd: str) -> None:
        self.child.sendline(cmd)
        time.sleep(.3)

    def close(self) -> None:
        self.child.close(force=True)


def verify_device(shell: Shell) -> str:
    bridge = shell.command("brctl show")
    address = shell.command("ifconfig br0")
    if DEVICE_MAC.lower() not in address.lower():
        raise SwitchError("br0 MAC 与 WN3000RP 实机记录不符")
    if "vlan1" not in bridge:
        raise SwitchError("设备没有预期的 vlan1 有线接口")
    return bridge + "\n" + address


def expect_psr(shell: Shell) -> None:
    state = verify_device(shell)
    if PSR_IP not in state or "eth1" not in state or "wl0.1" not in state:
        raise SwitchError("设备当前不是已知 PSR 状态；先重启恢复原厂功能")


def host_wifi_preflight(args: argparse.Namespace) -> str:
    active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                       check=False).stdout.splitlines()
    ethernet_connections = [line.rsplit(":", 1)[0] for line in active
                            if line.endswith(f":{args.ethernet}")]
    if ethernet_connections:
        if ethernet_connections == ["WN3000RP-test"]:
            run_local(["nmcli", "device", "disconnect", args.ethernet])
        elif ethernet_connections == [SHARE_NAME]:
            cleanup_host_share(args.ethernet)
        else:
            raise SwitchError(f"电脑有线口正在使用 {ethernet_connections}；请先断开其它连接")
    dev, host_ip = route_to(PSR_IP)
    if dev != args.wifi:
        raise SwitchError(f"访问 {PSR_IP} 走 {dev}，预期是 Wi-Fi {args.wifi}；不要让双网卡争同一网段")
    if not ipaddress.ip_address(host_ip) in ipaddress.ip_network("192.168.157.0/24"):
        raise SwitchError("电脑 Wi-Fi 不在已验证的测试热点网段")
    if not tcp_open(PSR_IP, 80):
        raise SwitchError("设备原厂管理页面不可达")
    if args.mode == "wisp" or args.share_computer:
        carrier = Path(f"/sys/class/net/{args.ethernet}/carrier")
        if not carrier.exists() or carrier.read_text().strip() != "1":
            raise SwitchError(f"请将电脑 {args.ethernet} 有线口接到 WN3000RP，再运行脚本")
    return host_ip


def wisp_preflight(shell: Shell, args: argparse.Namespace) -> bytes:
    route = shell.command("route -n")
    bssid = shell.command("wl -i eth1 bssid")
    address = shell.command("ifconfig br0")
    if TEST_GATEWAY not in route or f"inet addr:{PSR_IP}" not in address:
        raise SwitchError("当前上游 IP 或网关与已验证的测试热点参数不同，拒绝启动 WISP NAT")
    bssid_match = re.findall(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b", bssid)
    if len(bssid_match) != 1:
        raise SwitchError("无法确认设备 STA 当前关联的 BSSID")
    bssid_mac = bytes.fromhex(bssid_match[0].replace(":", ""))
    arp = shell.command("arp -n")
    if TEST_GATEWAY not in arp:
        shell.command(f"ping -c 1 -W 2 {TEST_GATEWAY}", timeout=5)
        arp = shell.command("arp -n")
    gateway_line = next((line for line in arp.splitlines()
                         if TEST_GATEWAY in line and
                         re.search(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b", line)), "")
    gateway_mac = re.search(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b", gateway_line)
    if not gateway_mac:
        raise SwitchError("无法确认测试网关的 ARP MAC")
    gateway_mac_bytes = bytes.fromhex(gateway_mac.group().replace(":", ""))
    if gateway_mac_bytes != bssid_mac:
        raise SwitchError("测试网关 MAC 与 STA BSSID 不同；当前 NAT 程序无法处理这条上游路径")
    wifi = run_local(["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", args.wifi]).stdout
    if "realmeGT7" not in wifi:
        raise SwitchError("电脑 Wi-Fi 当前未连接已验证的测试热点 realmeGT7")
    return gateway_mac_bytes


def runtime_nat_binary(gateway_mac: bytes, directory: Path) -> Path:
    source = TOOLS / "wispnat.mipsel"
    data = source.read_bytes()
    if len(gateway_mac) != 6 or data.count(ORIGINAL_GATEWAY_MAC) != 1:
        raise SwitchError("NAT 程序中的原始网关 MAC 不唯一，拒绝生成临时副本")
    output = directory / "wispnat.mipsel"
    output.write_bytes(data.replace(ORIGINAL_GATEWAY_MAC, gateway_mac, 1))
    return output


def upload(shell: Shell, host_ip: str, device_ip: str, source: Path, remote: str) -> None:
    if not source.is_file():
        raise SwitchError(f"缺少文件 {source}")
    server = subprocess.Popen(
        [sys.executable, str(TOOLS / "tftp_send_once.py"), str(source), remote,
         "--host", host_ip, "--device", device_ip],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        time.sleep(.2)
        output = shell.command(
            f"tftp -g -l /tmp/{remote} -r {remote} {host_ip} 1069", timeout=25
        )
        server_output, _ = server.communicate(timeout=7)
        if server.returncode or "Sent " not in server_output or "error" in output.lower():
            raise SwitchError(f"TFTP 上传 {remote} 失败：{server_output.strip()} {output.strip()}")
        size = source.stat().st_size
        actual = shell.command(f"ls -l /tmp/{remote}")
        if not re.search(rf"\s{size}\s", actual):
            raise SwitchError(f"设备上 /tmp/{remote} 大小异常")
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=3)


def stage(shell: Shell, host_ip: str, files: dict[str, Path]) -> None:
    for remote, source in files.items():
        upload(shell, host_ip, PSR_IP, source, remote)
    if "wispnat" in files:
        shell.command("chmod 700 /tmp/wispnat")


def save_log(mode: str, lines: list[str]) -> None:
    LOGS.mkdir(exist_ok=True)
    stamp = dt.datetime.now().astimezone().isoformat()
    path = LOGS / f"mode-switch-{mode}.txt"
    old = path.read_text() if path.exists() else ""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(old + "\n" + stamp + "\n" + "\n".join(lines) + "\n")


def create_host_share(ethernet: str) -> None:
    run_local(["nmcli", "connection", "delete", SHARE_NAME], check=False)
    run_local(["nmcli", "connection", "add", "type", "ethernet", "ifname", ethernet,
               "con-name", SHARE_NAME, "ipv4.method", "shared",
               "ipv4.addresses", "10.42.57.1/24", "ipv6.method", "disabled",
               "connection.autoconnect", "no"])
    run_local(["nmcli", "connection", "up", SHARE_NAME])


def cleanup_host_share(ethernet: str) -> None:
    active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                       check=False).stdout
    if f"{SHARE_NAME}:{ethernet}" in active.splitlines():
        run_local(["nmcli", "connection", "down", SHARE_NAME], check=False)
        run_local(["nmcli", "device", "disconnect", ethernet], check=False)
    run_local(["nmcli", "connection", "delete", SHARE_NAME], check=False)


def start_host_cleanup_monitor(ethernet: str) -> None:
    # Stop laptop DHCP if firmware reconstructs PSR or the device reboots.
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_monitor_ap",
                      "--ethernet", ethernet], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def start_wisp_cleanup_monitor(ethernet: str) -> None:
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_monitor_wisp",
                      "--ethernet", ethernet], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def start_mode(args: argparse.Namespace) -> None:
    host_ip = host_wifi_preflight(args)
    lines = [f"request: {args.mode}; host Wi-Fi {args.wifi}={host_ip}; Ethernet {args.ethernet}"]
    shell = None
    temporary_files = None
    try:
        enable_telnet(PSR_IP, args.username)
        shell = Shell(PSR_IP)
        expect_psr(shell)
        if args.mode == "wisp":
            gateway_mac = wisp_preflight(shell, args)
            lines.append(f"verified test gateway/BSSID {gateway_mac.hex(':')}")
        elif not args.share_computer:
            ethernet_state = shell.command("ifconfig vlan1")
            if "RUNNING" in ethernet_state:
                raise SwitchError("设备有线口现在有载波：先拔掉有线上联，再切换 AP，以免原厂 PSR 桥接两个网络")
        files = {}
        if args.mode == "wisp":
            temporary_files = tempfile.TemporaryDirectory(prefix="wn3000rp-nat-")
            files.update({
                "wispnat": runtime_nat_binary(gateway_mac, Path(temporary_files.name)),
                "wisp-apply.sh": TOOLS / "wisp-apply.sh",
                "wisp-udhcpd.conf": TOOLS / "wisp-udhcpd.conf",
            })
            lines.append("runtime NAT gateway MAC verified from STA BSSID and ARP")
        else:
            files["ap-apply.sh"] = TOOLS / "ap-apply.sh"
        stage(shell, host_ip, files)
        lines.append("TFTP files verified; no timed reboot")
        script = "wisp-apply.sh" if args.mode == "wisp" else "ap-apply.sh"
        log(f"切换 {args.mode}，设备 IP 即将改变……")
        shell.send_disruptive(f"sh /tmp/{script} >/tmp/{args.mode}-apply.log 2>&1 &")
        shell.close()
        shell = None
        time.sleep(2)
        if args.mode == "wisp":
            run_local(["nmcli", "connection", "up", "WN3000RP-test"], check=False)
            target = WISP_IP
            # The physical Ethernet must serve as downstream route.
            if wait_port(target, 80, 18):
                lines.append("WISP management reachable at 192.168.50.1:80")
                start_wisp_cleanup_monitor(args.ethernet)
            else:
                lines.append("WISP management not reached; manual reboot may be required")
                raise SwitchError("WISP 管理地址未出现；请断电重启设备以恢复原厂模式")
        else:
            target = AP_IP
            if args.share_computer:
                create_host_share(args.ethernet)
                lines.append("computer Ethernet shared at 10.42.57.1/24")
            if args.share_computer and not wait_port(target, 80, 12):
                raise SwitchError("AP 管理地址 10.42.57.2 不可达；请断电重启设备以恢复原厂模式")
            if args.share_computer:
                start_host_cleanup_monitor(args.ethernet)
                lines.append("AP management reachable at 10.42.57.2:80")
        log("切换命令已执行；没有自动重启定时器。断电重启或运行 restore 后恢复原厂 PSR。")
        log(f"当前设备管理地址：{target}；模式详情见 configs/{args.mode}/plan.md")
    except Exception as exc:
        lines.append(f"error: {exc}")
        if args.mode == "ap" and args.share_computer:
            # Never leave this computer serving DHCP if the device did not
            # reach the isolated AP bridge, or if a partial switch failed.
            cleanup_host_share(args.ethernet)
            lines.append("computer Ethernet share removed after failure")
        elif args.mode == "wisp":
            active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                               check=False).stdout
            if f"WN3000RP-test:{args.ethernet}" in active.splitlines():
                run_local(["nmcli", "device", "disconnect", args.ethernet], check=False)
                lines.append("computer WISP Ethernet test connection removed after failure")
        raise
    finally:
        if shell is not None:
            try:
                shell.command("killall utelnetd", timeout=2)
            except Exception:
                pass
            shell.close()
        if temporary_files is not None:
            temporary_files.cleanup()
        save_log(args.mode, lines)


def restore(args: argparse.Namespace) -> None:
    target = next((ip for ip in (WISP_IP, AP_IP, PSR_IP) if tcp_open(ip, 80)), None)
    if target is None:
        cleanup_host_share(args.ethernet)
        run_local(["nmcli", "device", "disconnect", args.ethernet], check=False)
        raise SwitchError("找不到设备；可直接断电重启，RAM 模式会消失")
    if target == PSR_IP:
        log("设备已处于原厂 PSR 管理地址")
        if tcp_open(PSR_IP, 23):
            shell = Shell(PSR_IP)
            verify_device(shell)
            shell.send_disruptive("killall utelnetd")
            shell.close()
    else:
        enable_telnet(target, args.username)
        shell = Shell(target)
        verify_device(shell)
        shell.send_disruptive("reboot")
        shell.close()
        log("已发送重启命令，等待原厂 PSR 恢复……")
        if not wait_port(PSR_IP, 80, 90):
            log("暂未探测到原厂管理页；请稍后检查或断电重启")
    cleanup_host_share(args.ethernet)
    run_local(["nmcli", "device", "disconnect", args.ethernet], check=False)
    if tcp_open(PSR_IP, 80):
        log(f"原厂管理页：http://{PSR_IP}/")
    save_log("restore", [f"restore requested from {target}; host share cleanup complete"])


def status() -> None:
    for label, ip in (("原厂 PSR", PSR_IP), ("WISP LAN", WISP_IP), ("有线 AP", AP_IP)):
        print(f"{label}: {ip} HTTP={'open' if tcp_open(ip,80) else 'closed'} Telnet={'open' if tcp_open(ip,23) else 'closed'}")
    print(run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"]).stdout.strip())


def monitor_ap(ethernet: str) -> None:
    failures = 0
    while True:
        time.sleep(15)
        active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                           check=False).stdout
        if f"{SHARE_NAME}:{ethernet}" not in active.splitlines():
            break
        try:
            shell = Shell(AP_IP)
            try:
                bridge = shell.command("brctl show")
            finally:
                shell.close()
            if "eth1" in bridge:
                break
            failures = 0
        except Exception:
            failures += 1
            if failures >= 3:
                break
    cleanup_host_share(ethernet)


def monitor_wisp(ethernet: str) -> None:
    failures = 0
    while True:
        time.sleep(15)
        active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                           check=False).stdout
        if f"WN3000RP-test:{ethernet}" not in active.splitlines():
            break
        if tcp_open(WISP_IP, 80):
            failures = 0
        else:
            failures += 1
            if failures >= 3 or tcp_open(PSR_IP, 80):
                break
    active = run_local(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                       check=False).stdout
    if f"WN3000RP-test:{ethernet}" in active.splitlines():
        run_local(["nmcli", "device", "disconnect", ethernet], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "wisp", "ap", "restore", "_monitor_ap", "_monitor_wisp"))
    parser.add_argument("--username", default="admin")
    parser.add_argument("--wifi", default="wlp1s0")
    parser.add_argument("--ethernet", default="eth0")
    parser.add_argument("--share-computer", action="store_true",
                        help="AP 测试时让本机 Wi-Fi 通过有线口提供上联 DHCP/NAT")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.mode == "_monitor_ap":
            monitor_ap(args.ethernet)
        elif args.mode == "_monitor_wisp":
            monitor_wisp(args.ethernet)
        elif args.mode == "status":
            status()
        elif args.mode == "restore":
            restore(args)
        else:
            start_mode(args)
    except (SwitchError, pexpect.ExceptionPexpect, subprocess.TimeoutExpired) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
