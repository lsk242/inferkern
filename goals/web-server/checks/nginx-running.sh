#!/bin/sh
# check: nginx is running (process exists) — must not false-positive on agent's own cmdline containing "nginx"
set -eu
if pgrep -x nginx >/dev/null 2>&1; then
  echo "nginx process found (pgrep -x)"
  exit 0
fi
# also accept: port 80 is listening with nginx worker
if ss -tlnp 2>&1 | grep -q ":80 " && ss -tlnp 2>&1 | grep -q "nginx"; then
  echo "port 80 listening with nginx"
  exit 0
fi
echo "nginx not running and port 80 not listening"
exit 1
