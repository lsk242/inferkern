#!/usr/bin/env bash
# Rerun from clean image N times, log success.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
N="${1:-2}"
IMAGE="${IMAGE:-inferkern:dev}"
PORT_BASE="${PORT_BASE:-18080}"
echo "==> harness: $N runs from clean image $IMAGE"
sudo docker build -t "$IMAGE" . 2>&1 | tail -5
PASS=0; FAIL=0
for i in $(seq 1 "$N"); do
  PORT=$((PORT_BASE + i))
  echo ""
  echo "--- run $i/$N (port $PORT) ---"
  CID=$(sudo docker run -d -p "$PORT:80" --rm "$IMAGE")
  OK=0
  for j in $(seq 1 30); do
    if curl -sf --max-time 2 "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
      echo "  run $i PASS (attempt $j)"
      PASS=$((PASS+1)); OK=1; break
    fi
    sleep 1
  done
  if [ "$OK" = "0" ]; then echo "  run $i FAIL"; sudo docker logs "$CID" 2>&1 | tail -20 || true; FAIL=$((FAIL+1)); fi
  sudo docker rm -f "$CID" >/dev/null 2>&1 || true
  sleep 1
done
echo ""
echo "=== harness result: $PASS/$N passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || { echo "HARNESS FAIL"; exit 1; }
echo "HARNESS PASS"
