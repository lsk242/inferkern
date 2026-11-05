#!/bin/sh
set -eu
if [ -f /tmp/inferkern-smoke/index.html ]; then
  echo "smoke file exists: /tmp/inferkern-smoke/index.html"
  exit 0
fi
echo "missing: /tmp/inferkern-smoke/index.html"
exit 1
