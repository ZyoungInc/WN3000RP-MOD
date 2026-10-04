# NETGEAR WN3000RP v1 原厂固件探索

状态：2026-10-04 电脑本地脚本已实测切换 **STA → NAT → 有线** 与 **有线 → AP 桥接**，并分别由脚本重启恢复原厂 PSR。当前设备 `192.168.157.22:80` 可达、TCP/23 关闭；电脑有线连接和临时共享均已断开，Wi-Fi 正常联网。原厂 Flash 只读镜像和官方固件已保存；未写 Flash、未擦除 MTD、未提交或修改 NVRAM。

## 实机确认

| 项目 | 结果 |
| --- | --- |
| 型号 / 固件 | WN3000RP / `V1.0.2.64_1.1.86` |
| SoC / CPU | Broadcom BCM5357 rev 2 / MIPS 74K |
| Kernel / BusyBox | Linux 2.6.22 / BusyBox 1.7.2 |
| Broadcom wl | 6.37.14.8 (`r440081`) |
| 内存 | `MemTotal` 30220 kB；采集时 `MemFree` 16448 kB |
| Flash | 4 MB；`boot` 256 KiB、`linux` 3008 KiB、内含 `rootfs` 约 2249 KiB，另有 board data、NVRAM 等分区 |
| 文件系统 | `/dev/root` SquashFS 只读；`/tmp` RAM 可写，`/var -> /tmp/var` |
| 初始 PSR 网络 | `br0=192.168.157.22/24`，MAC `20:E5:2A:02:15:D0`；上游网关 `192.168.157.245` |

以上来自本设备，不把其他版本的资料当作实测值。原始命令输出在 `logs/shell-info.txt`（含可能的设备凭据，权限 0600）。

## 服务与隐藏能力

- 初始仅 TCP/80 开放；TCP/21、22、23、53、443 及扫描范围内其他端口没有接受连接。UDP/53、1900 无回应，不能据此判定关闭。详情见 `logs/port-scan.txt`。
- Web 是设备内置 `httpd`；HTTP 响应未提供服务器版本。Basic realm 为 `NETGEAR WN3000RP`。菜单有连接现有网络、无线设置、IP 设置、状态、附属设备、备份/恢复、固件更新、WPS；常见 `debug.htm` 和 `diagnostics.htm` 页面返回 404。见 `logs/web-inventory.txt`。
- 实机命令清单与离线镜像均确认有 `telnetenabled`、`utelnetd`、`nvram`、`wl`、`wlconf`、`nas`、`eapd`、`udhcpd/udhcpc`、`brctl`、`vconfig`、`tftp`、`epi_ttcp`。镜像里未发现 `dropbear`、`wpa_supplicant`、`dnsmasq`、`pppd`、`iptables`、`ebtables`、`wget`、`nc`、`iperf` 可执行文件。
- 离线解包确认 `WLG_wds.htm`（WDS 点到点/点到多点设置）、`WLG_adv.htm`（AP 隔离设置）和 `debuginfo.htm`（仅显示 WAN 类型/型号）存在；`httpd` 字符串还包含 `wds.cgi`、`ca_hiddenpage.cgi`、`download_log.cgi`。这些入口在当前简化菜单中不可见，尚未执行 CGI。
- `wl cap` 包含 `ap`、`sta`、`psta`、`psr`。当前 `wl_mode=psr`，可同时 STA 与 AP；`wl wet`、`wl wet_tunnel` 查询返回 Unsupported。
- WISP 核查表明此固件虽有 `acos_service` 的 NAT 函数名，实际 `start_nat` / `mp_start_nat` / `mp_stop_nat` 是空实现；实机没有 `acos_nat.ko`、`/dev/acos_nat_cli`、iptables/conntrack 接口。见 `logs/wisp-acos-nat-stubs.txt`、`logs/wisp-nat-live.txt`。
- `ctf.ko` 已加载，旧版 Broadcom CTF 头文件定义了 SNAT/DNAT 加速动作；但当前固件没有创建 NAT 流的 netfilter/conntrack 或 ACOS NAT 实现，不能只改开关启用内核态 NAT。当前版本 GPL 源码链接返回 404，旧版 GPL 源码为不同内核。证据和限制见 `logs/wisp-kernel-nat-analysis.txt`。

## 临时 Telnet 开启与收尾

1. 确认目标为本设备的私网 IP/MAC，并先使用 LAN 物理连接。当前设备通过 `br0` 与上游 Wi-Fi 同桥，因此同一上游局域网里的主机也可能到达此私网地址；不应将它视为有 WAN 防火墙隔离的管理服务。
2. `tools/telnetenable_udp.py` 使用 NETGEAR TelnetEnable UDP/23 格式；当前固件接受设备当前 Web 管理凭据，旧 `Gearguy/Geardog` 组合未启用。脚本不保存密码，使用时从安全输入渠道传入。
3. 启用后 `utelnetd -d -i br0` 启动，无额外 shell 登录。采集命令见 `tools/collect_shell.py`，只执行只读查询。
4. WISP 与后续 AP 试验收尾均执行 `killall utelnetd`。AP 试验结束时 `10.42.57.2:23` 拒绝连接、80 仍开放；定时重启回 PSR 后 `192.168.157.22:23` 仍拒绝连接、Web 返回 HTTP 200。NVRAM 的 `telnetd_enable=0` 未持久化。

早期两轮试验仅修改运行时桥、IP、进程和 RAM 模块，当时的定时器到期后均已重启回到未改动的原厂配置。现用电脑脚本已按用户要求移除定时器，模式保持到断电重启或主动执行 `restore`。原厂配置备份在受限权限的 `logs/NETGEAR_WN3000RP.cfg`，**没有执行恢复**。

## 工作模式进度

| 模式 | 当前证据 | 尚需验证 |
| --- | --- | --- |
| 无线 STA → Ethernet | 原厂 PSR 已恢复；关闭电脑 Wi-Fi 后，有线 DHCP 得 `192.168.157.236`，能 ping 网关/公网并经 HTTPS 下载 | 多 MAC、IPv6、二层透明度、本地 iperf 吞吐 |
| WET/WDS | `wl wet` 和 `wl wet_tunnel` 返回 Unsupported，`wl wds` 可查询且当前为空 | WDS 对端兼容性；其它桥接实现 |
| **STA → NAT → Ethernet** | **已在测试热点临时验证，现已自动回退。** 测试时 `br0=192.168.50.1/24`，只含 `vlan1`；`eth1` STA 已移出桥；AP `wl0.1` 已关闭。电脑有线 DHCP 得 `.100`，第二个虚拟有线 MAC 得 `.103`，两者同时上网；关闭电脑 Wi-Fi 后，电脑仍经有线 DNS/ping/HTTPS 上网。上游发包实抓源 IP/MAC 均为设备自己的 `192.168.157.22` / `20:E5:2A:02:15:D0` | 上游租约更新、更多 UDP 应用、IPv6/分片、长时间稳定性、可移植配置 |
| 先前 AP 试验 | 用户确认手机 `.101` 可以上网；原厂 PSR 的 DHCP MAC 改写曾导致手机取不到地址，RAM 修复后可用 | 该 AP 已按最终需求关闭；不作为当前目标 |
| **Ethernet → AP** | **RAM 临时桥接已验证，现已自动回退。** 测试时 `br0` 仅含有线 `vlan1` 和 AP `wl0.1`；电脑有线提供测试网关/DHCP，手机连 `realmeGT7_EXT` 得 `10.42.57.64`，可打开网页与设备管理页 `10.42.57.2`。设备本身不做 NAT；临时测试所需 NAT 在电脑。 | 首次 STA 断连后观察到原厂服务重建 PSR，因果尚未确认；纯 AP 的持久模式、长期稳定性、IPv6/吞吐仍待验证。见 `configs/ap/plan.md`。 |

尚未进行任何校园网络认证或使用校园凭据。当前上游为测试 Wi-Fi；原厂状态页报告当前 STA 速率 78 Mbps，**不是吞吐测试结果**。

## 性能结果

尚无 iperf TCP/UDP 结果。同一 5 MB HTTPS 目标，原厂 PSR 有线三次为 **6.04、6.11、8.13 Mb/s**；关闭设备 AP 后经有线 NAT 的样本为 **2.74、10.34、约 6.15 Mb/s**，另有超时/TLS 失败。电脑直连测试 Wi-Fi 曾为 **20.16 Mb/s**，随后交替复测却仅约 **5–11 Mb/s**。这些外网应用层下载不能精确量化 NAT 与 PSR 的转发差异，临时 NAT 的偶发失败和功能缺口已确认。见 `logs/wisp-psr-comparison.txt`、`logs/wisp-ethernet-validation.txt`、`logs/wisp-kernel-nat-analysis.txt`。

## 固件镜像

- `firmware/original/mtd1-linux.bin`：只读 Flash dump，3,080,192 B，SHA-256 `96a94759ccb9dd66c84e5e9938090b2888abaec88b3dbb0bc9304bb1c1ead9c2`。
- `firmware/original/mtd2-rootfs.bin`：只读 Flash dump，2,303,716 B，SHA-256 `2fa495a1dfa537db8a95da1fa76500691e810cf2a240204895721a7a0d941850`。
- NETGEAR 发布了对应版本的[官方固件页面](https://kb.netgear.com/app/answers/detail/a_id/24670)，但当前电脑直连下载 ZIP 失败。设备内原始镜像已保存。
- `mtd2` 使用 `shsq` SquashFS 3.0/LZMA 变体。本机标准 `unsquashfs` 无法打开，已通过本地构建的 [sasquatch](https://github.com/devttys0/sasquatch) 解包至 `firmware/extracted/rootfs/`，并核实 ELF 为 **MIPS32 小端、o32 ABI、uClibc 动态链接**。见 `logs/firmware-analysis.txt`。`binwalk` 目前未安装。
- 用户放入了 `firmware/WN3000RP-V1.0.2.64_1.1.86.chk`，SHA-256 `85c0b8ba8cb00f1e6c2ae55041e5a2ff88385e67dd2d31cf22226dcf37237a2f`。其 58 字节 NETGEAR 头之后的 Linux 镜像与本机只读 `mtd1` 镜像前 2,969,600 字节一致。

## 尚未解决

1. 已有网络侧 shell，不需要第一阶段 TTL；启动串口日志尚无。见 `logs/bootlog.txt`。
2. 隐藏 Web CGI 的可达性与作用、二进制启动流程仍需审查。
3. 当前 PSR 的透明度、IPv6、多客户端和无线吞吐测试。
4. 当前 RAM NAT 对上游 DHCP 租约续租/热点地址变化、更多 UDP 应用、IPv6、IP 分片与长时稳定性的支持；校园网络类型和合法账号支持情况尚未涉及。
5. 纯有线 → AP 的稳定启动配置：本次仅通过临时 RAM 桥接验证；首次 STA 断连后观察到原厂服务恢复 PSR，触发条件尚需确认。单有线口仍能用同一 LAN 的管理 IP 管理设备。
6. 两种临时模式的本机切换脚本 `tools/mode_switch.py` 已在实机端到端验证。按用户后续要求，现版已移除 30 分钟自动重启；需断电重启或执行 `restore` 才回原厂 PSR。此前成功实测的是含定时器版本，移除定时器后的现版尚未重新实机切换。AP 桥接 `br0` 只含 `vlan1`、`wl0.1`；WISP `br0` 只含 `vlan1`，有线 DHCP 得 `192.168.50.100`，定向公网 ping 3/3、HTTPS 200。见 `configs/mode-switch.md` 和 `logs/mode-switch-*-validation.txt`。常驻网页方案已暂停，固件和 NVRAM 均未写入。

有线专用 WISP 的 RAM 操作、原始 NVRAM 值、回退方式与限制见 `configs/wisp/plan.md`；完整状态和上游源身份分别见权限 0600 的 `logs/wisp-ethernet-final-state.txt`、`logs/wisp-upstream-identity.txt`。电脑的 `WN3000RP-test` 有线 DHCP 连接目前已断开：原厂 PSR 下电脑 Wi-Fi 与有线会同时进入 `192.168.157.0/24`，NetworkManager 报告本机 Wi-Fi MAC 与有线 IP 冲突并撤掉有线路由。用有线测 PSR 时先断开电脑 Wi-Fi，结束后恢复。测试用的第二虚拟接口及定向路由已清理。

有线 → AP 的完整实验步骤、管理 IP、原厂服务自动重配现象及回退见 `configs/ap/plan.md`，实测结果见权限 0600 的 `logs/ap-validation.txt`。该模式只需桥接：上游有线网关发 DHCP，WN3000RP 的管理 IP 与客户端同处一个 LAN。测试用电脑 DHCP/NAT 已撤销。

电脑本地切换脚本：`python3 tools/mode_switch.py status` 查看当前状态；`python3 tools/mode_switch.py wisp` 测试 Wi-Fi → NAT → 有线；`python3 tools/mode_switch.py ap --share-computer` 使用电脑 Wi-Fi 为设备 AP 提供测试上联；`python3 tools/mode_switch.py restore` 重启恢复 PSR。切换时脚本提示输入原厂管理密码，不保存密码。使用前提、已验证范围和限制见 `configs/mode-switch.md`。

所有重要实测原始输出均在 `logs/`；逐步经过、限制与计划见 `notes.md`。配置目录保留给后续经过验证的模式配置。

公开仓库只包含脚本、源码和说明；本机的原始日志、配置备份、Flash 镜像及厂商固件不推送。克隆仓库后可参照 `logs/README.md` 和 `firmware/README.md` 了解缺失资料。
