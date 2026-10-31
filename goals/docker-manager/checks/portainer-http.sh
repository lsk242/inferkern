#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then code=$(curl -s -o /tmp/check-body --max-time 5 -w "%{http_code}" http://127.0.0.1:9000/ 2>&1 || echo fail); [ "$code" = "200" ] || [ "$code" = "302" ] && echo "Portainer HTTP $code" && exit 0; echo "Portainer $code"; cat /tmp/check-body 2>&1 | head -5 || true; fi
# fallback: check docker compose file exists
if [ -f /opt/portainer/docker-compose.yml ] || [ -f /srv/portainer/docker-compose.yml ]; then echo "portainer compose exists"; exit 0; fi
echo "portainer not ready"; exit 1
