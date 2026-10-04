#!/bin/sh
# Restore PSR topology from unchanged NVRAM by rebooting if test times out.
echo 'restore begin'
killall udhcpd 2>/dev/null
killall wispnat 2>/dev/null
brctl addif br0 eth1 2>/dev/null
ifconfig br0 192.168.157.22 netmask 255.255.255.0 up
route del default 2>/dev/null
route add default gw 192.168.157.245 dev br0
echo 1 > /proc/sys/net/ipv4/ip_forward
echo 'restore complete'
reboot
