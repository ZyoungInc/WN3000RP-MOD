# 有线口上联 → WN3000RP AP：RAM 临时验证

本文件记录早期带 30 分钟定时回退的实机试验。现用电脑脚本 `tools/mode_switch.py` 已按用户要求移除定时器；断电重启或运行 `restore` 才恢复 PSR。当前脚本说明见 `configs/mode-switch.md`。

2026-10-04 在本人测试热点上验证成功。电脑 Wi-Fi 接测试热点，电脑 Ethernet 经 NetworkManager `ipv4.method shared` 提供 `10.42.57.1/24`、DHCP 和临时 NAT；WN3000RP 仅把物理有线口 `vlan1` 与无线 AP `wl0.1` 放进 `br0`，设备自身不做 NAT。手机连接 `realmeGT7_EXT` 后获得 `10.42.57.64`，能打开网页，也能打开设备管理页 `http://10.42.57.2/`。电脑经有线口 ping 手机 3/3，设备管理页 HTTP 200。原始记录：`logs/ap-before.txt`、`logs/ap-bridge-transition.txt`、`logs/ap-second-apply.txt`、`logs/ap-validation.txt`。

## 本次运行时操作

1. 设备用 TelnetEnable 临时开启 shell，先保存运行状态；没有 `nvram set/commit` 或 Flash 操作。
2. 电脑启用临时共享连接 `WN3000RP-ap-share`，有线地址 `10.42.57.1/24`。这只是用于模拟有线网关：接真正的上游路由器时由上游提供 DHCP/网关。
3. 设备 RAM 中设管理别名 `ifconfig br0:ap 10.42.57.2 netmask 255.255.255.0 up`；停止设备自己的 `udhcpd`，执行 `brctl delif br0 eth1`。此后 `br0` 只有 `vlan1`、`wl0.1`。`wl0.1` 保持 WPA2 AP 工作。
4. **保留 `eth1` STA 的无线关联，但不让它参与数据桥。** 第一次试验额外执行 `wl -i eth1 disassoc` 后，原厂 `rc/mevent` 约数分钟内重建 PSR 桥、启动自己的 DHCP，手机又变回 `192.168.157.x`。第二次没有 disassoc，17:03–17:10 桥保持目标状态；触发条件仅从时间关联推测，尚未证明。

## 管理与回退

- 有线网络的网关/DHCP 是 `10.42.57.1`；WN3000RP 的管理地址是 `10.42.57.2`，不是网关。已从电脑和手机分别验证管理页可达，因此单有线口不妨碍管理。
- 本次所有设备变更仅在 RAM；启动了 `/tmp/wisp-timer` 30 分钟自动重启，或可手动重启，重启后按原 NVRAM 恢复 PSR。结束时须关闭临时 `utelnetd` 并复测 TCP/23。
- 主机临时 `WN3000RP-ap-share`、`WN3000RP-ap-control` 连接完成后删除，恢复电脑 Wi-Fi 正常联网；原厂 PSR 下应断开电脑有线连接，避免两个网卡进入相同 `192.168.157.0/24` 后争路由。

## 限制

- 这只验证了短时间有线 → AP 的桥接与 WPA2、DHCP、IPv4 网页、管理访问；未测试长期稳定性、IPv6 和吞吐。
- 原厂固件会在 STA 断连时重配网络，纯 AP 持久模式仍需查明原厂模式开关或启动流程。未经批准不修改 NVRAM 或 Flash。
- 本次手机上网的 NAT 在**电脑**，WN3000RP 不承担 NAT。若真正的有线上游已有路由器，设备只需桥接即可。
