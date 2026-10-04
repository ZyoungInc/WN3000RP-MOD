#!/bin/sh
# RAM-only: Ethernet vlan1 -> Wi-Fi AP wl0.1. Device reboot restores PSR.
# Keep the stock STA DHCP client and route intact: stopping them causes the
# firmware's network supervisor to rebuild its original PSR bridge.
ifconfig br0:ap 10.42.57.2 netmask 255.255.255.0 up || exit 1
brctl delif br0 eth1 || exit 1
brctl show
