#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/dns-body --max-time 5 -w "%{http_code}" http://127.0.0.1:8000/ 2>&1 || curl -s -o /tmp/dns-body --max-time 5 -w "%{http_code}" http://127.0.0.1:3000/ 2>&1 || echo fail); [ "$code" = "200" ] || [ "$code" = "302" ] && echo "DNS UI HTTP $code" && exit 0; fi
if docker ps 2>&1 | grep -qE "pihole|adguard"; then echo "pihole/adguard container"; exit 0; fi
if [ -f /etc/pihole/pihole-FTL.conf ] || [ -d /opt/AdGuardHome ]; then echo "pihole/adguard installed"; exit 0; fi
echo "dns filter not ready"; exit 1
