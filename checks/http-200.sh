#!/bin/sh
# Check: nginx serves HTTP 200 on localhost:80
set -e

# Check nginx is running (process exists or port 80 listening)
if ! pgrep nginx >/dev/null 2>&1; then
  # Fallback: check port
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -q ':80 ' || { echo "FAIL: nginx not listening on :80"; exit 1; }
  elif command -v netstat >/dev/null 2>&1; then
    netstat -tln 2>/dev/null | grep -q ':80 ' || { echo "FAIL: nginx not listening on :80"; exit 1; }
  else
    echo "FAIL: nginx process not found"
    exit 1
  fi
fi

# Check HTTP 200
if command -v curl >/dev/null 2>&1; then
  code=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1/ 2>&1) || code="000"
  if [ "$code" = "200" ]; then
    echo "PASS: HTTP $code on http://127.0.0.1/"
    exit 0
  else
    echo "FAIL: HTTP $code (expected 200)"
    exit 1
  fi
elif command -v wget >/dev/null 2>&1; then
  if wget -q --spider http://127.0.0.1/ 2>&1; then
    echo "PASS: wget succeeded on http://127.0.0.1/"
    exit 0
  else
    echo "FAIL: wget failed on http://127.0.0.1/"
    exit 1
  fi
else
  echo "FAIL: no curl or wget available"
  exit 1
fi
