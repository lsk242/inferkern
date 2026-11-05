#!/bin/bash
# scripts/demo.sh — one-shot demos (what "has been done")
# Usage:
#   ./scripts/demo.sh smoke          # smoke-test local (no Docker, ~1s)
#   ./scripts/demo.sh smoke-docker   # smoke-test Docker (~2s)
#   ./scripts/demo.sh web            # web-server local dry-run (shows plan, no side effects)
#   ./scripts/demo.sh web-docker     # web-server Docker heuristic (real nginx, exit after converge)
#   ./scripts/demo.sh web-serve      # web-server detached on :8080, curl it, keep Up
#   ./scripts/demo.sh all            # run all of the above in sequence
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; [ -f .env ] && . .env; set +a

cmd="${1:-help}"
run() { echo ""; echo ">>> $*"; "$@"; }

case "$cmd" in
  smoke)
    echo "== smoke-test local (host heuristic, no Docker) =="
    run python3 -m inferkern.agent.loop goals/smoke-test/goal.yaml --no-llm
    run curl -s http://127.0.0.1:8765/ | head -c 400; echo
    echo "Try: pkill -f 'http.server 8765'  # to stop"
    ;;
  smoke-docker)
    echo "== smoke-test Docker (heuristic) =="
    run sudo docker run --rm -e INFERKERN_GOAL=/goals/smoke-test/goal.yaml -v "$ROOT/goals:/goals:ro" -p 8765:8765 inferkern:dev
    ;;
  web)
    echo "== web-server local dry-run (no side effects) =="
    run python3 -m inferkern.agent.loop goals/web-server/goal.yaml --dry-run --no-llm --max-steps 5
    ;;
  web-docker)
    echo "== web-server Docker heuristic (real converge, exit) =="
    run sudo docker run --rm -e INFERKERN_GOAL=/goals/web-server/goal.yaml -v "$ROOT/goals:/goals:ro" inferkern:dev
    ;;
  web-serve)
    echo "== web-server detached on :8080 (keep-alive) =="
    sudo docker rm -f inferkern-web-test 2>&1 | true
    run sudo docker run -d --name inferkern-web-test -p 8080:80 -v "$ROOT/goals:/goals:ro" inferkern:dev
    echo "Waiting 6s for nginx..."
    sleep 6
    run sudo docker logs inferkern-web-test | tail -5
    run curl -s http://127.0.0.1:8080/ | head -c 500; echo
    run sudo docker ps | grep inferkern-web-test
    echo "Stop with: sudo docker rm -f inferkern-web-test"
    ;;
  all)
    "$0" smoke; pkill -f "http.server 8765" 2>&1 | true; sleep 0.5
    "$0" smoke-docker
    "$0" web
    "$0" web-docker
    "$0" web-serve
    ;;
  help|*)
    echo "Usage: $0 {smoke|smoke-docker|web|web-docker|web-serve|all}"
    echo "  smoke         smoke-test local (no Docker)"
    echo "  smoke-docker  smoke-test Docker"
    echo "  web           web-server dry-run"
    echo "  web-docker    web-server Docker heuristic"
    echo "  web-serve     web-server detached on :8080 + curl"
    echo "  all           run all"
    ;;
esac
