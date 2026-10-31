#!/bin/sh
set -eu
if [ -f /etc/caddy/Caddyfile ] && grep -q "reverse_proxy" /etc/caddy/Caddyfile 2>/dev/null; then echo "caddy reverse_proxy found"; exit 0; fi
if [ -f /etc/traefik/traefik.yml ] || [ -f /etc/traefik/dynamic.yml ]; then echo "traefik config"; exit 0; fi
if nginx -t 2>&1 | grep -q "successful"; then echo "nginx proxy config ok"; exit 0; fi
echo "proxy config missing"; exit 1
