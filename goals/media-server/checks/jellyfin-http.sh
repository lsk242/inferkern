#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/jf-body --max-time 5 -w "%{http_code}" http://127.0.0.1:8096/ 2>&1 || echo fail); [ "$code" = "200" ] || [ "$code" = "302" ] && echo "Jellyfin HTTP $code" && exit 0; echo "Jellyfin $code"; fi
# fallback: check service
if pgrep -f jellyfin >/dev/null 2>&1; then echo "jellyfin process"; exit 0; fi
if [ -f /etc/jellyfin/system.xml ]; then echo "jellyfin config"; exit 0; fi
echo "jellyfin not ready"; exit 1
