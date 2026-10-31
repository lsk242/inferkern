#!/bin/sh
set -eu
echo "[entrypoint] inferkern Docker entrypoint starting"
GOAL="${INFERKERN_GOAL:-/etc/inferkern/goal.md}"
STATE_DIR="${INFERKERN_STATE_DIR:-/var/lib/inferkern}"
mkdir -p "$STATE_DIR"
echo "[entrypoint] GOAL=$GOAL STATE_DIR=$STATE_DIR"
if [ -n "${LLM_API_KEY:-}" ]; then echo "[entrypoint] LLM_API_KEY=*** (present)"; else echo "[entrypoint] LLM_API_KEY not set — stub/dry-run mode"; fi
if [ -n "${LLM_ENDPOINT:-}" ]; then echo "[entrypoint] LLM_ENDPOINT=$LLM_ENDPOINT"; fi

set +e
python3 -m agent --goal "$GOAL" --state-dir "$STATE_DIR"
CODE=$?
set -e

if [ $CODE -eq 0 ]; then
  echo "[entrypoint] agent converged — keeping nginx alive"
  if [ "${INFERKERN_ONESHOT:-}" = "1" ]; then
    # Stay alive briefly so harness can verify HTTP before container exits
    echo "[entrypoint] INFERKERN_ONESHOT=1 — serving for 30s then exiting"
    if pgrep nginx >/dev/null 2>&1; then
      nginx -s stop 2>/dev/null || true; sleep 1
    fi
    nginx 2>/dev/null || true
    for i in $(seq 1 30); do
      if [ $i -eq 30 ]; then echo "[entrypoint] oneshot window done — exiting"; exit 0; fi
      sleep 1
    done
  fi
  if pgrep nginx >/dev/null 2>&1; then
    nginx -s stop 2>/dev/null || nginx -s quit 2>/dev/null || pkill nginx 2>/dev/null || true
    sleep 1
  fi
  echo "[entrypoint] container ready — serving on :80"
  exec nginx -g 'daemon off;' 2>&1 || { while true; do sleep 3600; done; }
else
  echo "[entrypoint] agent failed with code $CODE"
  exit $CODE
fi
