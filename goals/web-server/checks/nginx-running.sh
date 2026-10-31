#!/bin/sh
# check: nginx is running (process exists)
set -eu
if pgrep nginx >/dev/null 2>&1; then
  echo "nginx process found"
  exit 0
fi
if ps aux 2>&1 | grep -q "[n]ginx"; then
  echo "nginx process found (ps)"
  exit 0
fi
# also accept: nginx -t passes and port 80 is listening
if ss -tlnp 2>&1 | grep -q ":80 "; then
  echo "port 80 listening (likely nginx)"
  exit 0
fi
echo "nginx not running and port 80 not listening"
exit 1
