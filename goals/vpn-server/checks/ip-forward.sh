#!/bin/sh
set -eu
if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" = "1" ]; then echo "ip_forward=1"; exit 0; fi
echo "ip_forward not enabled"; exit 1
