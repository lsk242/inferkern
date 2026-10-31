#!/bin/sh
# check: HTTP 200 on localhost:80
set -eu
# try curl, then wget, then nc
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /tmp/check-http-body --max-time 5 -w "%{http_code}" http://127.0.0.1/ 2>&1 || echo "curl_fail")
  if [ "$code" = "200" ]; then
    echo "HTTP 200 OK (curl)"
    exit 0
  fi
  echo "curl returned: $code"
  cat /tmp/check-http-body 2>&1 | head -20 || true
elif command -v wget >/dev/null 2>&1; then
  if wget -qO- --timeout=5 http://127.0.0.1/ >/tmp/check-http-body 2>&1; then
    echo "HTTP OK (wget)"
    exit 0
  fi
  echo "wget failed"
else
  echo "no curl or wget available"
  exit 1
fi
exit 1
