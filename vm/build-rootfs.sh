#!/bin/bash
# vm/build-rootfs.sh — Build an Alpine rootfs tarball for QEMU using Docker export.
# Requires: docker (or podman). Output: vm/rootfs/ and vm/rootfs.tar
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
OUT="$SCRIPT_DIR/rootfs"
TARBALL="$SCRIPT_DIR/rootfs.tar"

echo "[vm/build-rootfs] building Alpine rootfs via Docker..."

if command -v docker >/dev/null 2>&1; then
  DOCKER=docker
elif command -v podman >/dev/null 2>&1; then
  DOCKER=podman
else
  echo "error: need docker or podman to build rootfs" >&2
  echo "hint: on a machine with docker, run: make vm-build" >&2
  exit 1
fi

# Use the same base as docker/Dockerfile for parity
BASE="alpine:3.20"

echo " -> pulling $BASE"
$DOCKER pull "$BASE"

# Create a throwaway container and export it
CID=$($DOCKER create "$BASE" /bin/sh -c "apk add --no-cache python3 py3-yaml nginx curl wget ca-certificates openrc busybox-openrc iproute2 procps-ng util-linux bash openssh 2>&1 | tail -5; mkdir -p /etc/inferkern /var/lib/inferkern /srv/http /goals /state /run/openrc; touch /run/openrc/softlevel; echo built")
echo " -> container $CID"

# Install deps inside container via docker exec not possible on create-only; do a run+commit approach:
$DOCKER rm "$CID" >/dev/null 2>&1 || true

# Instead: run, install, commit, export
CID=$($DOCKER run -d "$BASE" sleep 300)
echo " -> installer container $CID"
$DOCKER exec "$CID" sh -c '
  set -e
  apk add --no-cache python3 py3-yaml nginx curl wget ca-certificates openrc busybox-openrc iproute2 procps-ng util-linux bash openssh 2>&1 | tail -20
  pip3 install --no-cache-dir --break-system-packages httpx rich 2>&1 | tail -5 || pip3 install --no-cache-dir httpx rich 2>&1 | tail -5 || echo "pip install optional failed, continuing"
  mkdir -p /etc/inferkern /var/lib/inferkern /srv/http /goals /state /run/openrc
  touch /run/openrc/softlevel
  echo "<!doctype html><html><body><h1>inferkern VM placeholder</h1></body></html>" > /srv/http/index.html
'
# copy in the inferkern package + goals
$DOCKER cp "$ROOT/inferkern" "$CID:/app/inferkern" 2>/dev/null || {
  # create /app if missing
  $DOCKER exec "$CID" mkdir -p /app
  $DOCKER cp "$ROOT/inferkern" "$CID:/app/inferkern"
}
$DOCKER cp "$ROOT/goals" "$CID:/app/goals"
$DOCKER cp "$ROOT/pyproject.toml" "$CID:/app/pyproject.toml" 2>/dev/null || true
$DOCKER exec "$CID" sh -c 'mkdir -p /goals; cp -r /app/goals/* /goals/ 2>/dev/null; chmod +x /app/goals/*/checks/*.sh 2>/dev/null; chmod +x /goals/*/checks/*.sh 2>/dev/null; echo "PYTHONPATH=/app" >> /etc/environment; mkdir -p /usr/local/bin'
$DOCKER exec "$CID" sh -c 'cat > /usr/local/bin/inferkern-init << "INIT"
#!/bin/sh
# QEMU init: minimal PID1 setup then hand to supervisor
echo "[inferkern-init] starting (PID \$\$)"
# Bring up loopback
ip link set lo up 2>/dev/null || true
# Trigger mdev
echo /sbin/mdev > /proc/sys/kernel/hotplug 2>/dev/null || true
mdev -s 2>/dev/null || true
# Mount state disk if present (second disk) — try to find a writable ext4 volume
for dev in /dev/vdb /dev/sdb /dev/vda2; do
  if [ -b "\$dev" ]; then
    echo "[inferkern-init] trying state disk \$dev"
    mkdir -p /var/lib/inferkern
    if mount -t ext4 "\$dev" /var/lib/inferkern 2>/dev/null; then
      echo "[inferkern-init] mounted state disk \$dev"
      break
    fi
    # if not formatted, format it
    if ! blkid "\$dev" 2>/dev/null | grep -q ext4; then
      echo "[inferkern-init] formatting \$dev as ext4"
      mkfs.ext4 -F "\$dev" 2>&1 | tail -5
      mount -t ext4 "\$dev" /var/lib/inferkern 2>&1 | tail -5
      break
    fi
  fi
done
exec python3 -m inferkern.supervisor.sup --no-mounts
INIT
chmod +x /usr/local/bin/inferkern-init
'

# export filesystem
rm -rf "$OUT" "$TARBALL"
mkdir -p "$OUT"
echo " -> exporting to $TARBALL"
$DOCKER export "$CID" | tar -x -C "$OUT" 2>&1 | tail -5
$DOCKER export "$CID" > "$TARBALL"
$DOCKER rm -f "$CID" >/dev/null 2>&1 || true

echo "[vm/build-rootfs] done: $OUT ($(du -sh "$OUT" | cut -f1)) tarball $(du -sh "$TARBALL" | cut -f1)"
echo "Next: make vm-run  (needs qemu-system-x86_64)"
