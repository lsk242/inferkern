#!/bin/sh
set -eu
if command -v nft >/dev/null 2>&1 && nft list ruleset 2>&1 | grep -q "table"; then echo "nft ruleset loaded"; exit 0; fi
if iptables -L 2>&1 | grep -q "Chain"; then echo "iptables loaded"; exit 0; fi
echo "no firewall rules"; exit 1
