#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/prom-body --max-time 5 -w "%{http_code}" http://127.0.0.1:9090/-/healthy 2>&1 || echo fail); [ "$code" = "200" ] && echo "prometheus healthy" && exit 0; fi
if pgrep -f prometheus >/dev/null 2>&1; then echo "prometheus process"; exit 0; fi
if ss -tlnp 2>&1 | grep -q ":9090"; then echo "prometheus :9090"; exit 0; fi
echo "prometheus not ready"; exit 1
