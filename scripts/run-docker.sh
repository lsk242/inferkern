#!/usr/bin/env bash
# Build and run the Docker image, wait for HTTP 200, print result.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
IMAGE="${IMAGE:-inferkern:dev}"
PORT="${PORT:-18080}"
echo "==> docker build $IMAGE"
sudo docker build -t "$IMAGE" . 2>&1 | tail -8
echo "==> docker run (port $PORT -> 80)"
CID=$(sudo docker run -d -p "$PORT:80" --rm "$IMAGE")
echo "    container $CID"
cleanup() { sudo docker rm -f "$CID" >/dev/null 2>&1 || true; }
trap cleanup EXIT
echo "==> waiting for HTTP 200 on http://127.0.0.1:$PORT/ (max 30s)"
for i in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    echo "PASS: HTTP 200 on attempt $i"
    curl -s "http://127.0.0.1:$PORT/" | head -3
    sudo docker logs "$CID" 2>&1 | tail -20 || true
    exit 0
  fi
  sleep 1
done
echo "FAIL: no HTTP 200 after 30s"
sudo docker logs "$CID" 2>&1 | tail -40 || true
exit 1
