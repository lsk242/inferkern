#!/bin/sh
set -eu
if [ -f /etc/dnsmasq.conf ] || [ -f /etc/NetworkManager/system-connections/* ] 2>/dev/null; then echo "network config exists"; exit 0; fi
if grep -q "dhcp-range" /etc/dnsmasq.conf 2>/dev/null; then echo "dhcp-range found"; exit 0; fi
if [ -f /etc/dhcp/dhcpd.conf ]; then echo "dhcpd.conf found"; exit 0; fi
echo "no network config"; exit 1
