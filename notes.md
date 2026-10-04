# 探索记录

## 2026-10-04：网络发现与只读 shell

- 本机有线接口 `enxc84d442339ca`（Realtek r8152 USB Ethernet），地址 `192.168.157.236/24`；Wi-Fi `wlp1s0` 关闭，未发现 USB 串口。网关和 DHCP/DNS 是 `192.168.157.245`。原始状态见 `logs/network-discovery.txt`。
- 设备 `192.168.157.22`、MAC `20:E5:2A:02:15:D0`。扫描 TCP 1–1024 及 18 个常见高端口，仅 80 开放；UDP 53/1900 无回应，状态未确定。见 `logs/port-scan.txt`。
- Web Basic 认证。设备状态页显示 WN3000RP、固件 `V1.0.2.64_1.1.86`、GUI `V1.0.2.56_2.1.9.5`，当前是连接上游 Wi-Fi 的扩展器；上游报告链路速率 78 Mbps。页面索引见 `logs/web-inventory.txt`。
- 仅以设备所有者提供的管理账号构造一次有效 NETGEAR TelnetEnable UDP/23 报文；旧版 `Gearguy/Geardog` 未奏效。Telnet shell 无二次登录提示，启动命令为 `utelnetd -d -i br0`。只读采集保存到权限 0600 的 `logs/shell-info.txt`。NVRAM 原始输出可能有凭据，请勿公开。
- 实机：Broadcom BCM5357 rev 2、MIPS 74K、Linux 2.6.22、BusyBox 1.7.2、Broadcom wl 6.37.14.8。总 RAM 30220 kB，采集时空闲 16448 kB。根文件系统 SquashFS 只读；`/tmp` 为 RAM，`/var` 指向 `/tmp/var`。
- `wl cap` 含 `ap sta ... psta psr`；当前 `wl_mode=psr`，`wl psta` 返回 2，`wl wet` 和 `wl wet_tunnel` 均返回 Unsupported。桥 `br0` 包含 `vlan1`、`eth1`、`wl0.1`。本机从上游 DHCP 获得 `192.168.157.236`，能 ARP/ping 上游 `192.168.157.245`，表明当前 Ethernet→Wi-Fi 扩展模式至少能传 IPv4。尚不能断言为完全透明二层桥；IPv6 和多个有线客户端未测。
- 只读下载了 `/dev/mtd1ro` 和 `/dev/mtd2ro` 到 `firmware/original/`。`mtd2` 与 `mtd1` 中从偏移 `0xBD91C` 开始的内容完全一致。`mtd2` 头为 `shsq`；本机标准 `unsquashfs` 无法识别，随后本地编译兼容的 `sasquatch`，成功解包到 `firmware/extracted/rootfs/`。官方相同版本 ZIP 有 NETGEAR 下载链接，但当前 Linux 直连下载失败。
- 离线 ELF 检查确认 **MIPS32 小端、o32 ABI、动态链接 uClibc**。原厂启动由 `/sbin/rc` 二进制管理，未找到传统 `rcS`。`httpd` 中发现 `wds.cgi`、`ca_hiddenpage.cgi`、`download_log.cgi` 等字符串，离线页面有 WDS 与 AP 隔离配置。见 `logs/firmware-analysis.txt`。
- 结束时执行 `killall utelnetd`，复测 TCP/23 为拒绝连接。未修改 NVRAM 或 Flash；`telnetd_enable` 保持 0。

## 待验证

- 设备是否存在可用的原厂 WET 真二层模式；目前 getter 返回 Unsupported。
- 当前 PSR 模式的下游 MAC 映射、IPv6 透传和多客户端行为。
- 隐藏 CGI 的可达性、具体调用作用及 `/sbin/rc` 启动逻辑。
- AP、WISP 和校园 Wi-Fi 模式；需要对应合法网络参数后才测试。
- 吞吐、延迟、丢包、CPU 压力测试；当前没有第二台独立有线客户端/测试服务端。

## 2026-10-04：测试热点上的 RAM NAT 与有线专用模式

- 设备重启后临时重启 Telnet；先保存完整 NVRAM、接口、桥、wl 状态到权限 0600 的 `logs/wisp-before.txt`，不 `commit`。官方同版本 `.chk` 已由用户放入 `firmware/`，校验与本机只读 MTD1 前缀一致。
- 实机 `/proc/net/ip_tables_*`、conntrack、`/dev/acos_nat_cli` 不存在，模块只有 `br_dns_hijack`、`br_dhcp_filter`、`wl`、`et`、`ctf`。对当前镜像 `acos_service` 反汇编确认 NAT 入口为空函数。没有找到可复用的原厂 NAT。
- 构建了 6 KB 左右的静态 MIPS o32 无 libc RAM NAT，用旧内核原始 packet socket 收发。最初探针确认 `AF_PACKET` 可用；现代静态 glibc 二进制在 Linux 2.6.22 上段错误，因此使用原始 syscall。二进制和源码放在 `tools/`。程序只支持该测试热点固定上游 IP/网关 MAC，以及 IPv4 TCP、UDP、ICMP echo；这不是通用生产路由实现。
- 切换时先启动 RAM 回退定时器；临时将 `eth1` STA 从 `br0` 移出，`br0` 改为 `192.168.50.1/24`，原厂 `udhcpd` 给下游发地址，用户态程序做源地址/端口 NAT。首次转换到期后按原厂 NVRAM 重启回 PSR，证明自动回退可用；第二轮重新进入并验证。
- AP 试验中，手机 DHCP 首次失败，获得 `169.254.224.135`。抓包发现手机 AP MAC `CE:7F:…` 被原厂 PSR 路径改为 DHCP 回复目标 `CC:7F:…`。RAM 中卸载 `br_dhcp_filter`，并用临时程序按 DHCP 事务 ID 修回复目标 MAC/BOOTP chaddr 后，手机得到 `.101` 正式租约；用户确认可以上网，但感觉慢。
- 用户明确收窄为 **Wi-Fi STA → NAT → 仅 Ethernet**。执行 `brctl delif br0 wl0.1` 和 `wl -i wl0.1 bss down`；STA 保持关联。停止 AP 专用 DHCP 修复进程，重新加载原厂 `br_dhcp_filter`。此时 `br0` 仅有 `vlan1`。
- 实体电脑有线 DHCP 获得 `192.168.50.100`。用同电脑第二个 macvlan MAC 模拟另一有线客户端，得到 `.103`，两者同时分别完成 8/8 次公网 ping 和 HTTPS 200。上游 `eth1` 抓到这些出站流量仅使用设备的 MAC `20:E5:2A:02:15:D0` 与 IP `192.168.157.22`。后续关闭电脑 Wi-Fi，删除第二虚拟客户端，只保留实体有线 `.100`，DNS、公网 3/3 ping、HTTPS 200 仍通过。随后恢复电脑 Wi-Fi。证据见 `logs/wisp-ethernet-validation.txt` 与 `logs/wisp-upstream-identity.txt`。
- 5 MB HTTPS 对照下载：电脑直连测试 Wi-Fi 20.16 Mb/s；设备 AP 关闭后的用户态 NAT 两次 2.74 / 10.34 Mb/s。测试条件、波动与 CPU 样本见 `logs/wisp-ethernet-performance.txt`。这些不是 iperf 结果。
- 测试用 macvlan 与定向路由均已清理。电脑保留 `WN3000RP-test` 有线 DHCP 连接，Wi-Fi 在时默认经 Wi-Fi；Wi-Fi 断开后默认经有线设备。本轮设备 Flash/NVRAM 零修改；有线专用配置和回退方案见 `configs/wisp/plan.md`。当前临时测试仅覆盖此热点和短时间，不构成可持久化的通用方案。
- 最终于约 15:08 CST 重新启动 30 分钟 RAM 回退定时器，保存 `logs/wisp-ethernet-final-state.txt`，关闭临时 `utelnetd`；TCP/23 拒绝连接，TCP/80 和 LAN ping 正常。预计约 15:38 CST 自动重启并恢复原厂 PSR。

## 2026-10-04：内核态 NAT 与 PSR 速度核查

- 离线检查 `ctf.ko`、`et.ko`、`wl.ko` 的符号与 NETGEAR 旧版 GPL 头文件：CTF 设计有 SNAT/DNAT 动作，但本机缺少 netfilter/conntrack NAT 和 ACOS NAT 实现。当前版本 GPL 下载链接返回 404；1.0.1.34 与 1.0.1.36 源码均是 Linux 2.4.20，不能直接为实机 2.6.22 编译模块。未加载来源不明的 `.ko`。证据见 `logs/wisp-kernel-nat-analysis.txt`。
- RAM 定时器约 15:38 CST 触发重启并恢复原厂 PSR；`192.168.157.22:80` 再次开放、TCP/23 拒绝连接。有线 DHCP 重新获得 `192.168.157.236`。
- 电脑 Wi-Fi 与有线同时在 `192.168.157.0/24` 时，NetworkManager 报告有线 `.236` 与电脑自己的 Wi-Fi MAC 冲突，撤掉有线路由。短暂关闭电脑 Wi-Fi 并重新 DHCP 后，有线公网 ping 3/3，5 MB HTTPS 三次为 6.04、6.11、8.13 Mb/s。测试后电脑 Wi-Fi 已恢复、有线连接已断开。原始证据见 `logs/wisp-psr-comparison.txt`。
- 外网下载源波动大，当前数据不能证明 PSR 比临时 NAT 快多少；临时 NAT 偶发超时/TLS 失败。要量化路径开销需要上游侧独立 iperf 服务端。当前设备与电脑均已退出临时测试状态。

## 2026-10-04：有线口上联 → AP 的 RAM 桥接验证

- 用户询问唯一有线口能否做 AP 上联，以及改成桥接后如何管理。电脑 Wi-Fi 接测试热点，Ethernet 开 NetworkManager 临时共享，提供 `10.42.57.1/24`、DHCP 和测试用 NAT。设备 `br0` 留 `vlan1` 与 `wl0.1`，移出 STA `eth1`；设备 DHCP 关闭，管理别名为 `10.42.57.2/24`。未修改 NVRAM/Flash。
- 首次另外让 STA `disassoc` 后，设备原厂服务自行恢复 PSR 桥并重新启动 `udhcpd`，手机从短暂的 `10.42.57.x` 变为 `192.168.157.237`。设备未重启；`rc/mevent` 是否直接由 disassoc 触发尚需确认。证据在 `logs/ap-auto-restore.txt`。
- 第二次保留 STA 关联但不接入数据桥，17:03–17:10 桥持续只有 `vlan1`、`wl0.1`。电脑的 DHCP 日志确认 iPad 获得 `10.42.57.64`；电脑到手机 ping 3/3，设备管理 `10.42.57.2` 返回 HTTP 200。用户确认手机网页与该管理页都能打开。证据在 `logs/ap-second-apply.txt`、`logs/ap-validation.txt`。
- 本次 WN3000RP 不做 NAT；手机上网的 NAT 在电脑。单有线口仍可通过同一二层 LAN 访问设备管理页。短时可用，纯 AP 持久配置和长期稳定性未测。配置、风险与回退见 `configs/ap/plan.md`。
- 17:19 CST，RAM 回退定时器重启设备，`192.168.157.22` 管理页 HTTP 200、TCP/23 拒绝连接。电脑 `eth0` 已断开，临时 `WN3000RP-ap-share` 与 `WN3000RP-ap-control` 连接已删除，Wi-Fi 默认路由仍经测试热点。最终证据追加在 `logs/ap-validation.txt`。

## 2026-10-04：电脑本地切换脚本

- 用户最终选择电脑本地脚本，不再制作常驻设备的网页或自定义固件。`tools/mode_switch.py` 包装 TelnetEnable、TFTP RAM 上传、目标 MAC/PSR 检查、测试热点参数核对、30 分钟设备端回退、电脑 NetworkManager 临时共享及清理；用法见 `configs/mode-switch.md`。网页原型及私人访问令牌已从工作目录删除。
- 初次 `ap --share-computer` 因设备本次启动的 TelnetEnable 已使用过而安全退出。重启后第一次 AP 脚本在停止 `udhcpc` 后被原厂服务重建 PSR；移除这一操作并保留上游 STA 关联/租约后，AP 脚本端到端成功：`br0` 仅 `vlan1`、`wl0.1`，`10.42.57.2` HTTP 200，20 秒后仍稳定。`restore` 成功重启回 PSR 并删除电脑共享。见 `logs/mode-switch-ap-validation.txt`。
- WISP 脚本起初因热点重连后 BSSID/网关 MAC 变化而安全拒绝。改为启动时核对设备 BSSID 与网关 ARP，并只在电脑临时副本中替换 NAT 二进制的网关 MAC。第一次自动 WISP 仍因停止原厂 `udhcpc` 后重建 PSR 而失败；保留 `udhcpc` 后，修正的切换流程和完整 `mode_switch.py wisp` 均成功。电脑有线 DHCP 得 `192.168.50.100`，经有线公网 ping 3/3、HTTPS 200，设备桥仅有 `vlan1`，RAM NAT 和 DHCP 进程正常；再次 `restore` 回 PSR。证据见 `logs/mode-switch-wisp-validation.txt`。
- 最终复测 `192.168.157.22:80` HTTP 200、TCP/23 关闭；电脑 Wi-Fi 有默认路由，有线断开，无临时 AP 共享配置。两种脚本只验证短时测试热点；WISP 上游 DHCP 续租、IPv6/分片及长期稳定性未验证。
- 设备或网络模式脚本没有写 Flash/NVRAM 命令。原版本的 `--share-computer` 会创建本机 DHCP/NAT 共享，后台监控在设备重建 PSR 桥、失联或到 27 分钟时撤销；WISP 原版本也会在设备自动回退/失联后断开电脑有线配置。后续改动见下一节。

## 2026-10-04：取消电脑脚本的自动定时回退

- 用户明确要求模式保持到自行断电重启。已从 `tools/mode_switch.py` 删除 `wisp-timer.mipsel` 上传、30 分钟定时器启动、27/31 分钟电脑监控截止时间；AP/WISP 脚本不再依赖定时器。`restore` 仍可主动发重启命令，断电重启也会清空 RAM 模式。
- 电脑侧监控继续检查设备失联/原厂桥重建，目的是清理电脑临时 DHCP 共享或有线测试连接，不会触发设备重启。当前设备处于 PSR，管理页 `192.168.157.22:80` 可达、Telnet 关闭、电脑有线连接断开。取消定时器后的版本尚未重新实机切换验证；此前成功端到端验证使用的是旧版定时器。
