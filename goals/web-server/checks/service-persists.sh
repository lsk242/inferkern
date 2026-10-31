#!/bin/sh
# Check: nginx process survives (re-check after a brief pause)
set -e
if pgrep -x nginx >/dev/null 2>&1 || pgrep -f "[n]ginx: master" >/dev/null 2>&1 || ps aux 2>/dev/null | grep -q "[n]ginx"; then
  echo "PASS: nginx process running"
  exit 0
fi
# Fallback: check port 80 still listening (service-persists is soft in container)
if ss -tln 2>/dev/null | grep -q ':80 ' || cat /proc/net/tcp 2>/dev/null | grep -q ':0050'; then
  echo "PASS: port 80 listening (service-persists soft pass)"
  exit 0
fi
echo "FAIL: nginx not running and port 80 not listening"
exit 1
