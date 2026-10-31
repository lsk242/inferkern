#!/bin/sh
set -eu
if pgrep -x caddy >/dev/null 2>&1 || pgrep -f caddy >/dev/null 2>&1; then echo "caddy running"; exit 0; fi
if pgrep -f traefik >/dev/null 2>&1; then echo "traefik running"; exit 0; fi
if ss -tlnp 2>&1 | grep -q ":80 " || ss -tlnp 2>&1 | grep -q ":443 "; then echo "proxy port listening"; exit 0; fi
if [ -f /etc/caddy/Caddyfile ] || [ -f /etc/traefik/traefik.yml ]; then echo "proxy config"; exit 0; fi
echo "reverse proxy not running"; exit 1
