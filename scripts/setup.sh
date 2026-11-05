#!/bin/bash
# scripts/setup.sh — first-time setup for inferkern on Ubuntu 26.04
# Installs host deps, Python deps, builds Docker image and VM rootfs.
# Usage: ./scripts/setup.sh            # full setup
#        ./scripts/setup.sh --no-vm     # skip VM build (faster, no guestfs)
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; [ -f .env ] && . .env; set +a

NO_VM=false
for a in "$@"; do [ "$a" = "--no-vm" ] && NO_VM=true; done

echo "== inferkern setup =="
echo "Root: $ROOT"
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo ""
echo "--- 1/4  host deps (docker, qemu, make, libguestfs) ---"
if [ "$(id -u)" = 0 ]; then
  bash /home/lsk/install-inferkern-deps.sh
else
  if command -v docker >/dev/null 2>&1 && command -v qemu-system-x86_64 >/dev/null 2>&1 && command -v make >/dev/null 2>&1; then
    echo "host deps already present (docker, qemu, make)"
  else
    echo "Need host deps — run: sudo bash /home/lsk/install-inferkern-deps.sh"
    echo "Or: sudo bash scripts/setup.sh  (as root will install host deps)"
    # don't fail, continue to Python deps
  fi
fi

echo ""
echo "--- 2/4  Python deps ---"
if [ -f pyproject.toml ]; then
  pip install -e . 2>&1 | tail -5 || pip install pyyaml httpx rich 2>&1 | tail -5
else
  pip install pyyaml httpx rich 2>&1 | tail -5
fi
python3 -m pytest -q 2>&1 | tail -5

echo ""
echo "--- 3/4  Docker image (inferkern:dev, Alpine 3.20) ---"
if docker ps >/dev/null 2>&1 || sudo docker ps >/dev/null 2>&1; then
  DOCKER="docker"; docker ps >/dev/null 2>&1 || DOCKER="sudo docker"
  $DOCKER build -f docker/Dockerfile -t inferkern:dev . 2>&1 | tail -5
  echo "Docker OK: inferkern:dev built"
else
  echo "Docker not available — skip (image will be built on first make docker-build)"
fi

echo ""
echo "--- 4/4  VM rootfs + kernel (optional) ---"
if [ "$NO_VM" = true ]; then
  echo "skip (--no-vm)"
else
  if command -v guestfish >/dev/null 2>&1 || command -v qemu-img >/dev/null 2>&1; then
    bash vm/build-rootfs.sh 2>&1 | tail -10 || echo "VM build failed (see above) — Docker demos still work"
    ls -lh vm/rootfs.tar vm/vmlinuz-virt 2>&1 | head -5 || true
  else
    echo "qemu not available — skip VM build"
  fi
fi

echo ""
echo "== setup done =="
echo "Try:"
echo "  ./scripts/demo.sh smoke          # local, no Docker"
echo "  ./scripts/demo.sh web-serve      # Docker :8080"
echo "  ./scripts/test-all.sh            # full suite"
