#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/ha-body --max-time 5 -w "%{http_code}" http://127.0.0.1:8123/ 2>&1 || echo fail); [ "$code" = "200" ] || [ "$code" = "302" ] && echo "HA HTTP $code" && exit 0; fi
if docker ps 2>&1 | grep -q "homeassistant"; then echo "HA container"; exit 0; fi
if [ -f /srv/homeassistant/configuration.yaml ]; then echo "HA config"; exit 0; fi
echo "homeassistant not ready"; exit 1
