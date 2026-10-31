#!/bin/sh
# Check: the served page contains expected content marker
set -e

MARKER="${1:-inferkern}"

if command -v curl >/dev/null 2>&1; then
  body=$(curl -sf http://127.0.0.1/ 2>&1) || { echo "FAIL: curl failed"; exit 1; }
elif command -v wget >/dev/null 2>&1; then
  body=$(wget -qO- http://127.0.0.1/ 2>&1) || { echo "FAIL: wget failed"; exit 1; }
else
  echo "FAIL: no curl or wget"
  exit 1
fi

if echo "$body" | grep -qi "$MARKER"; then
  echo "PASS: content contains '$MARKER'"
else
  echo "FAIL: content does not contain '$MARKER'"
  echo "Body preview: $(echo "$body" | head -c 200)"
  exit 1
fi
