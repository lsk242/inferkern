#!/bin/sh
set -eu
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /tmp/check-http-body --max-time 5 -w "%{http_code}" http://127.0.0.1/ 2>&1 || echo "curl_fail")
  if [ "$code" = "200" ]; then echo "HTTP 200 OK"; exit 0; fi
  echo "curl returned: $code"
fi
if command -v wget >/dev/null 2>&1; then
  if wget -qO- --timeout=5 http://127.0.0.1/ >/tmp/check-http-body 2>&1; then echo "HTTP OK (wget)"; exit 0; fi
fi
echo "http check failed"; exit 1
