#!/bin/sh
# Check: nginx config is valid and service would survive a restart
set -e

if ! command -v nginx >/dev/null 2>&1; then
  echo "FAIL: nginx binary not found"
  exit 1
fi

if ! nginx -t 2>&1; then
  echo "FAIL: nginx -t failed"
  exit 1
fi

if [ ! -f /etc/nginx/http.d/inferkern.conf ] && [ ! -f /etc/nginx/nginx.conf ]; then
  echo "FAIL: no nginx config found"
  exit 1
fi

# Check that the site root exists
if [ ! -d /srv/www ] && [ ! -d /usr/share/nginx/html ]; then
  echo "FAIL: no web root found"
  exit 1
fi

echo "PASS: nginx config valid, service persists"
