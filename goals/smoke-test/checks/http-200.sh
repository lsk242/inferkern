#!/bin/sh
set -eu
# Check a Python http.server on 8765 (smoke test) or 80 (real web-server)
for port in 8765 80; do
  if command -v curl >/dev/null 2>&1; then
    code=$(curl -s -o /tmp/check-smoke-body --max-time 3 -w "%{http_code}" http://127.0.0.1:$port/ 2>&1 || echo "curl_fail")
    if [ "$code" = "200" ]; then
      echo "HTTP 200 OK on :$port (curl)"
      exit 0
    fi
  elif command -v wget >/dev/null 2>&1; then
    if wget -qO- --timeout=3 http://127.0.0.1:$port/ >/tmp/check-smoke-body 2>&1; then
      echo "HTTP OK on :$port (wget)"
      exit 0
    fi
  fi
done
echo "no HTTP 200 on :8765 or :80"
exit 1
