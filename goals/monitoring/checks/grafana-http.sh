#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/graf-body --max-time 5 -w "%{http_code}" http://127.0.0.1:3000/login 2>&1 || echo fail); [ "$code" = "200" ] || [ "$code" = "302" ] && echo "grafana HTTP $code" && exit 0; fi
if pgrep -f grafana >/dev/null 2>&1; then echo "grafana process"; exit 0; fi
if [ -f /etc/grafana/grafana.ini ]; then echo "grafana config"; exit 0; fi
echo "grafana not ready"; exit 1
