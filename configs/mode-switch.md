# 电脑本地临时模式切换脚本

脚本：`tools/mode_switch.py`。适用本项目的 WN3000RP v1 与当前测试热点 `realmeGT7`；只上传到设备 `/tmp`、只改运行时桥/IP/进程。**不写 Flash、不执行 `nvram set/commit`。没有自动重启定时器；设备保持当前模式，直到断电重启或运行 `restore`，随后恢复原厂 PSR。**

在本项目目录运行：

```sh
python3 tools/mode_switch.py status
python3 tools/mode_switch.py wisp
python3 tools/mode_switch.py ap --share-computer
python3 tools/mode_switch.py restore
```

运行 `wisp` 或 `ap --share-computer` 时，电脑 `wlp1s0` 要连测试热点，`eth0` 要插在设备唯一的 Ethernet 口。脚本会断开既有的 `WN3000RP-test` 有线连接，避免电脑双网卡同时占用 `192.168.157.0/24`。脚本提示输入原厂 Web 管理密码；密码不写入脚本或日志。电脑需要 Python 3、`cryptography`、`pexpect`、`telnet`、`nmcli`；TFTP 用仓库已有纯 Python 工具。可用 `--wifi`、`--ethernet` 指定其它网卡。

| 命令 | 运行时拓扑 | 管理地址 | 电脑动作 |
| --- | --- | --- | --- |
| `wisp` | 测试 Wi-Fi STA → RAM 用户态 NAT → 设备 Ethernet | `192.168.50.1` | 激活已有的 `WN3000RP-test` 有线 DHCP 配置，并在设备重启/失联后自动断开 |
| `ap --share-computer` | 电脑 Wi-Fi → 电脑 NAT/DHCP → Ethernet → 设备 AP | `10.42.57.2` | 创建临时 `WN3000RP-ap-script` 共享配置；仅在设备重启、失联或桥被原厂服务重建时撤销 |
| `ap` | 现成有线网关 → Ethernet → 设备 AP | 切换时设备设 `10.42.57.2` RAM 管理别名 | 切换前必须先拔掉设备 Ethernet 上联，切换完成后再接有线网关，避免原厂 PSR 暂时桥接两个网络。有线上游需提供 DHCP；非 `10.42.57.0/24` 的管理地址仍需另行规划，当前脚本尚未自动适配。 |
| `restore` | 重启回原厂 PSR | 原厂地址 `192.168.157.22` | 删除本脚本的共享配置并断开有线测试连接 |

每次切换前都会检查设备 MAC、PSR 桥、测试热点路由等。切换后没有超时回退；若控制连接中断或切换失败，直接断电重启即可恢复原厂 PSR，上传到 `/tmp` 的文件也会消失。`status` 不启用 Telnet。`restore` 在设备可达时发重启命令并清理电脑网络配置；如果设备不可达，也会清理电脑网络配置，此时需断电重启设备。

切换期间临时 Telnet 会保持开启，供 AP 桥接监控检查设备是否被原厂服务重配；这个服务没有二次登录。重启设备后 Telnet 与 `/tmp` 中的程序一同消失。请只在可信的测试 LAN 使用，结束时重启或运行 `restore`。

`wisp` **严格绑定本次测试热点参数**：设备上游 `192.168.157.22`、网关 `192.168.157.245` 和热点 SSID `realmeGT7`。启动时它核对设备 STA 的 BSSID 与网关 ARP MAC，再在电脑临时副本中替换 NAT 程序的网关 MAC；原始二进制保持不变。上游 IP/网关地址变化或租约续期仍可能中断。当前 NAT 仅支持部分 IPv4 TCP/UDP/ICMP，不支持 IPv6/分片。不得在未验证的校园网络使用，更不能据此规避身份、设备数量或计费限制。

`ap --share-computer` 在电脑本地运行监控进程：若设备原厂服务重建含 `eth1` 的 PSR 桥、设备失联或共享连接已被移除，就撤销电脑临时 DHCP/NAT，以免误把它桥到上游测试 Wi-Fi。这个监控不设时间上限。电脑睡眠、断电或监控进程被强杀时无法保证自动清理；此时运行 `restore`，或手动运行 `nmcli connection delete WN3000RP-ap-script` 并断开电脑有线口。WISP 的电脑有线测试连接也由无时间上限的监控在设备失联/重启后断开。

2026-10-04 实机端到端验证：`ap --share-computer` 创建 `10.42.57.1/24` 电脑共享，设备 `br0` 仅有 `vlan1`、`wl0.1`，`10.42.57.2` 管理页 HTTP 200；20 秒后仍保持，`restore` 回 PSR 并清理共享。`wisp` 给电脑 DHCP `192.168.50.100`，设备 `br0` 仅有 `vlan1`，定向经有线公网 ping 3/3、HTTPS 200；`restore` 再次回 PSR。最终 `192.168.157.22:80` 开放、TCP/23 关闭、电脑有线断开。见 `logs/mode-switch-ap-validation.txt`、`logs/mode-switch-wisp-validation.txt`。**这两次成功测试使用的是旧的 30 分钟回退版本；按用户后续要求移除定时器的版本尚未重新实机切换测试。**独立有线上游的 `ap`（不带 `--share-computer`）尚未通过此脚本端到端测试；此前只验证过同一桥接拓扑。以上验证均为短时间测试，未覆盖 DHCP 续租和长期稳定性。
