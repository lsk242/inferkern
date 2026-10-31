#!/bin/sh
set -eu
if ss -tlnp 2>&1 | grep -q ":53 "; then echo "DNS :53 listening"; exit 0; fi
if [ -f /etc/pihole/gravity.db ] || [ -f /opt/AdGuardHome/AdGuardHome.yaml ]; then echo "blocklist present"; exit 0; fi
echo "DNS blocking not ready"; exit 1
