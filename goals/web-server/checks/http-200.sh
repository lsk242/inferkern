#!/bin/sh
# Check: HTTP 200 on localhost:80
set -e
URL="${CHECK_URL:-http://127.0.0.1:80/}"
if command -v curl >/dev/null 2>&1; then
  code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 5 "$URL" 2>/dev/null || true)
  if [ "$code" = "200" ]; then
    echo "PASS: HTTP 200 on $URL"
    exit 0
  else
    echo "FAIL: HTTP $code on $URL (expected 200)"
    exit 1
  fi
elif command -v wget >/dev/null 2>&1; then
  if wget -q --spider --timeout=5 "$URL" 2>/dev/null; then
    echo "PASS: HTTP reachable on $URL (wget)"
    exit 0
  else
    echo "FAIL: HTTP not reachable on $URL (wget)"
    exit 1
  fi
else
  # Fallback: check if something is listening on :80
  if ss -tln 2>/dev/null | grep -q ':80 ' || netstat -tln 2>/dev/null | grep -q ':80 ' || cat /proc/net/tcp 2>/dev/null | grep -q ':0050'; then
    echo "PASS: port 80 listening (no HTTP client available)"
    exit 0
  fi
  echo "FAIL: no HTTP client and port 80 not listening"
  exit 1
fi
