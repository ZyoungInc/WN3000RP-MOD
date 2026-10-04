# Wi-Fi STA → Ethernet NAT 临时试验与持久化前检查

状态：2026-10-04，测试 Wi-Fi 上的 RAM 试验已结束。有线专用模式曾验证、AP 曾关闭；早期试验约 15:38 CST 自动重启并恢复原厂 PSR，临时 Telnet 关闭且 TCP/23 拒绝连接。**没有改写 Flash、提交 NVRAM 或恢复配置。** 本文记录历史试验拓扑，当前设备不在 WISP 模式；现用电脑脚本已按用户要求移除 30 分钟定时器，详见 `configs/mode-switch.md`。该方案只适用于当前测试热点参数，不能据此直接持久化。

## 实机拓扑

| 用途 | 接口与地址 | 实际状态 |
| --- | --- | --- |
| 上游 STA | `eth1`，MAC `20:E5:2A:02:15:D0` | 从 `br0` 移除；原始 DHCP 租约 IP `192.168.157.22/24` 由 RAM NAT 程序用于发包；内核未在 `eth1` 配 IP |
| 上游网关 | `192.168.157.245` | 原始 RAM NAT 二进制写有首次实测 MAC `0A:3C:63:86:4D:9F`；电脑切换脚本启动时以当前 BSSID/ARP 核对并替换临时上传副本的 MAC，本轮为 `12:B9:1B:AB:A1:0A` |
| 下游 LAN | `br0=192.168.50.1/24` | **仅有线 `vlan1`**；不含 `eth1` 和 `wl0.1` |
| 下游 DHCP | `192.168.50.100–199` | 原厂 `udhcpd`，配置在 `/tmp/wisp-udhcpd.conf` |
| 下游 AP | `wl0.1` | `brctl delif br0 wl0.1`、`wl -i wl0.1 bss down`，STA 仍在线 |

## 原厂 NAT 判定

原厂 `acos_service` 含 `mp_start_nat`、`mp_stop_nat` 名称，但本机镜像反汇编确认入口直接返回。实机没有 `/dev/acos_nat_cli`、`acos_nat.ko`、`ip_tables`/conntrack 接口。`router_disable=0` 在原始 PSR 状态已经如此，不能把它当作 WISP 开关。证据：`logs/wisp-nat-live.txt`、`logs/wisp-nat-extra.txt`、`logs/wisp-acos-nat-stubs.txt`。

`ctf.ko` 已加载，旧版 Broadcom CTF 头文件支持 SNAT/DNAT 动作，但本机固件缺少为其建立 NAT 连接流的组件。不能只安装 `iptables` 用户态程序或改 NVRAM 开关启用内核态 NAT；精确版本的 GPL 内核源码链接已失效，旧版源码内核为 2.4.20。见 `logs/wisp-kernel-nat-analysis.txt`。

## NVRAM

本轮 **零项 NVRAM 修改**，也没有 `nvram commit`。关键原值均保留：

| 变量 | 原值 | 临时试验中的 NVRAM 值 |
| --- | --- | --- |
| `router_disable` | `0` | 不变 |
| `wan_ifname` / `wan_ifnames` | `br0` / `vlan2` | 不变；实际运行接口由 RAM 命令调整 |
| `lan_ifname` / `lan_ifnames` | `br0` / `vlan1 eth1 wl0.1` | 不变；实际从桥中移除 `eth1` |
| `lan_ipaddr` / `lan_netmask` | `192.168.1.250` / `255.255.255.0` | 不变；实际 `br0` 暂设 `192.168.50.1/24` |
| `lan_proto` / `wan_proto` | `dhcp` / `dhcp` | 不变 |
| `wan_ipaddr` / `wan_gateway` | `192.168.157.22` / `192.168.157.245` | 不变 |
| `wl_mode` / `wl0_mode` / `wl0.1_mode` | `psr` / `psr` / `ap` | 不变 |

完整原值在权限 0600 的 `logs/wisp-before.txt`，含 Wi-Fi 凭据，不能公开。

## RAM 启动顺序

相关源码、编译好的 MIPS ELF 和脚本在 `tools/`：

1. 上传 `wispnat.mipsel`、`wisp-timer.mipsel`、`wisp-apply.sh`、`wisp-restore.sh`、`wisp-udhcpd.conf` 到设备 `/tmp`。`tools/tftp_send_once.py` 可从测试电脑提供文件。所有目标路径均是 RAM。`wisp-dhcp-rewrite.mipsel` 只用于此前 AP 测试，有线专用模式不用。
2. 启动 `/tmp/wisp-timer`，30 分钟后自动运行 `/tmp/wisp-restore.sh`；回退脚本先恢复桥/IP，再重启，以使用未改动的原厂 NVRAM 启动。观察到 `ps` 中定时器进程后才切换。
3. 执行 `sh /tmp/wisp-apply.sh`：停止 `udhcpc`；删除默认路由；临时关闭内核 IPv4 forwarding；`brctl delif br0 eth1`；`ifconfig br0 192.168.50.1 netmask 255.255.255.0 up`；启动 `udhcpd` 与 RAM NAT。转发由用户态 raw packet sockets 完成，内核 `ip_forward=0` 是避免重复转发。
4. `brctl delif br0 wl0.1`，再 `wl -i wl0.1 bss down`，实际验证 STA 仍关联测试热点。原厂 `br_dhcp_filter` 保持加载；AP 模式曾需额外的 DHCP MAC 修复，**有线专用模式无需运行**，本轮已停止修复进程并重新加载过滤模块。`wl0.1` 的关闭没有写入 NVRAM。
5. 有线客户端从 DHCP 自动拿 `192.168.50.x/24`，网关 `192.168.50.1`，DNS `192.168.157.245`。测试结束后执行回退脚本或直接重启；本轮已关闭 `utelnetd` 并复测 TCP/23 拒绝连接。

测试电脑现有 `WN3000RP-test` NetworkManager 配置绑定有线 MAC `C8:4D:44:23:39:CA`、DHCP 自动、route metric 800、DNS 自动。该连接**当前已断开**；原厂 PSR 下电脑 Wi-Fi 与有线同处 `192.168.157.0/24` 会触发本机 ARP 地址冲突，导致有线路由撤销。测试 PSR 有线时短暂断开电脑 Wi-Fi 并重新 DHCP，结束后恢复 Wi-Fi。有线配置在 RAM NAT 模式下曾正常承担默认路由。此前增加的静态 `192.168.50.2`、`/32` 路由及第二个 macvlan 已删除。见 `logs/wisp-psr-comparison.txt`。

## 验证结果

- 用户确认手机通过原 AP 试验的 `192.168.50.101` 可以上网，但速度慢；随后目标收窄为**仅有线输出**，AP 关闭。
- 物理电脑有线 DHCP 得 `192.168.50.100`。独立虚拟有线 MAC `C8:4D:44:23:39:CB` 得 `192.168.50.103`；两者同时分别完成公网 ping 和 HTTPS。模拟客户端仍在同一台电脑上，见 `logs/wisp-ethernet-validation.txt`。
- 临时关闭电脑 Wi-Fi 后，电脑只保留有线 `192.168.50.100` 和默认路由 `192.168.50.1`；DNS、3/3 次公网 ping、HTTPS 200 均成功。随后恢复了电脑 Wi-Fi。
- `eth1` 上游侧实抓包显示发往两个不同目标的流量源 MAC 都是 `20:E5:2A:02:15:D0`、源 IP 都是 `192.168.157.22`。这支持**经本 NAT 路径的下游设备共用设备上游身份**；电脑 Wi-Fi 在并发测试时本身也独立连接同一热点，因此该测试不能证明热点全局只看到一台设备。见 `logs/wisp-upstream-identity.txt`。
- 5 MB HTTPS 传输：电脑直连测试 Wi-Fi 约 20.16 Mb/s；有线专用 NAT 两次约 2.74 与 10.34 Mb/s，波动大。详见 `logs/wisp-ethernet-validation.txt`、`logs/wisp-ethernet-performance.txt`。无 iperf 数据。

## 已观察到的边界

- 用户态 NAT 已验证 IPv4 ICMP、HTTP、HTTPS 和 UDP DNS；两 MAC 同时流量通过。尚未验证其它 UDP 应用；IPv6 和 IP 分片当前程序不支持，不能把当前程序当成完整路由器固件。
- 上游 IP `192.168.157.22` 写在 RAM NAT ELF 中；网关 MAC 在启动时由电脑脚本以实测 BSSID/ARP 更新临时上传副本。运行期间没有独立 DHCP 租约续租/动态更新；租约到期、热点换地址或网关 MAC 变化会中断连接。
- AP 试验曾在 RAM 中卸载 `br_dhcp_filter` 并运行 DHCP MAC 修复；有线专用模式已重新加载原厂模块并关闭修复进程。重启后原厂 PSR 中继模式恢复。
- 本轮没有可提交的 NVRAM 变量变更。若今后需要常驻 WISP，须先解决租约维护、异常恢复、用户态 NAT 完整性和启动程序的存放方式，再另行提出具体永久化方案并取得批准。
