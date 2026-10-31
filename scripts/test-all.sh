#!/bin/bash
# scripts/test-all.sh — run every inferkern test that has been done
# Usage: ./scripts/test-all.sh              # local + docker (if available)
#        ./scripts/test-all.sh --no-docker  # local only
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load .env if present (doesn't fail if missing)
set -a; [ -f .env ] && . .env; set +a
# Ensure docker detection works with or without sudo
DOCKER_OK=false
if docker ps >/dev/null 2>&1 || sudo docker ps >/dev/null 2>&1; then DOCKER_OK=true; fi

NO_DOCKER=false
for a in "$@"; do [ "$a" = "--no-docker" ] && NO_DOCKER=true; done
if [ "$NO_DOCKER" = true ]; then DOCKER_OK=false; fi

fail=0
say() { echo ""; echo "==== $* ===="; }
say_ok() { echo "PASS: $*"; }
say_fail() { echo "FAIL: $*"; fail=1; }

say "1/7  pytest (14 tests)"
if timeout 30 python3 -m pytest -q; then say_ok "pytest"; else say_fail "pytest"; fi

say "2/7  smoke-test local (no Docker, no LLM) — heuristic on host"
rm -rf /tmp/state-test-local /tmp/inferkern-smoke 2>&1 | true
if timeout 15 python3 -m inferkern.agent.loop goals/smoke-test/goal.yaml --no-llm --state-dir /tmp/state-test-local --max-steps 10 2>&1 | tail -5; then
  if curl -sf http://127.0.0.1:8765/ 2>&1 | grep -q "inferkern smoke"; then say_ok "smoke-test local + curl"; else say_fail "smoke-test local curl"; fi
else say_fail "smoke-test local run"; fi
pkill -f "http.server 8765" 2>&1 | true; sleep 0.3

say "3/7  smoke-test Docker (heuristic)"
if [ "$DOCKER_OK" = true ]; then
  if timeout 15 sudo docker run --rm -e INFERKERN_GOAL=/goals/smoke-test/goal.yaml -e INFERKERN_KEEP_ALIVE=0 -v "$ROOT/goals:/goals:ro" inferkern:dev 2>&1 | grep -q "All checks passed"; then say_ok "smoke-test docker"; else say_fail "smoke-test docker"; fi
else echo "skip (no docker)"; fi

say "4/7  web-server Docker (heuristic, nginx)"
if [ "$DOCKER_OK" = true ]; then
  if timeout 15 sudo docker run --rm -e INFERKERN_GOAL=/goals/web-server/goal.yaml -e INFERKERN_KEEP_ALIVE=0 -v "$ROOT/goals:/goals:ro" inferkern:dev 2>&1 | grep -q "All checks passed"; then say_ok "web-server docker"; else say_fail "web-server docker"; fi
else echo "skip (no docker)"; fi

say "5/7  web-server detached + curl on :8080"
if [ "$DOCKER_OK" = true ]; then
  sudo docker rm -f inferkern-web-test 2>&1 | true
  sudo docker run -d --name inferkern-web-test -p 8080:80 -v "$ROOT/goals:/goals:ro" inferkern:dev >/dev/null
  sleep 6
  if curl -sf http://127.0.0.1:8080/ 2>&1 | grep -q "inferkern"; then say_ok "web-server detached curl"; else say_fail "web-server detached curl"; fi
  if sudo docker ps 2>&1 | grep -q inferkern-web-test; then say_ok "container still Up"; else say_fail "container not Up"; fi
  sudo docker rm -f inferkern-web-test 2>&1 | true
else echo "skip (no docker)"; fi

say "6/7  harness (Proposal D) — local + docker"
if timeout 60 python3 -m harness.run --goal smoke-test --runs 2 2>&1 | grep -q "2/2 passed"; then say_ok "harness smoke local"; else say_fail "harness smoke local"; fi
if [ "$DOCKER_OK" = true ]; then
  if timeout 60 python3 -m harness.run --goal web-server --runs 1 --docker 2>&1 | grep -q "1/1 passed"; then say_ok "harness web docker"; else say_fail "harness web docker"; fi
else echo "skip harness docker (no docker)"; fi

say "7/7  VM artifacts (build-rootfs)"
if [ -f vm/rootfs.tar ] && [ -f vm/vmlinuz-virt ]; then say_ok "vm rootfs.tar + vmlinuz-virt present ($(du -h vm/rootfs.tar | cut -f1) + $(du -h vm/vmlinuz-virt | cut -f1))"; else echo "skip (run make vm-build first)"; fi

echo ""
if [ $fail -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit $fail
