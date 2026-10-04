#!/bin/sh
# Volatile test only. Device reboot restores PSR.
echo 'switch begin'
# Keep the stock DHCP client running while changing the bridge. Stopping it
# causes the firmware supervisor to rebuild the PSR bridge immediately.
echo 0 > /proc/sys/net/ipv4/ip_forward
echo 'forwarding disabled'
brctl delif br0 eth1 || exit 1
echo 'STA removed from bridge'
ifconfig br0 192.168.50.1 netmask 255.255.255.0 up || exit 1
echo 'LAN address set'
brctl delif br0 wl0.1 || exit 1
echo 'AP removed from bridge'
wl -i wl0.1 bss down || exit 1
echo 'AP stopped'
udhcpd /tmp/wisp-udhcpd.conf
echo 'DHCP server started'
/tmp/wispnat >/tmp/wispnat.log 2>&1
echo 'switch complete'
