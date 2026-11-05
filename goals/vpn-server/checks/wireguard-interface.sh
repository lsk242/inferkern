#!/bin/sh
set -eu
if ip link show wg0 2>&1 | grep -q "wg0"; then echo "wg0 exists"; exit 0; fi
if wg show 2>&1 | grep -q "interface"; then echo "wg interface"; exit 0; fi
if [ -f /etc/wireguard/wg0.conf ]; then echo "wg0.conf exists"; exit 0; fi
echo "wireguard not configured"; exit 1
