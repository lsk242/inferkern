#!/bin/sh
# Build Alpine mini rootfs for QEMU boot.
# Tries Docker first, falls back to local apk.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT="$ROOT_DIR/qemu/rootfs"
ALPINE_VERSION="3.20"

usage() {
  echo "Usage: $0 [--output DIR] [--alpine-version VER]"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --alpine-version) ALPINE_VERSION="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

echo "[build-rootfs] Alpine $ALPINE_VERSION -> $OUTPUT"

if command -v docker >/dev/null 2>&1; then
  echo "[build-rootfs] using Docker..."

  cat > /tmp/Dockerfile.inferkern-rootfs << DOCKERFILE
FROM alpine:$ALPINE_VERSION
RUN apk add --no-cache \
    alpine-base \
    linux-virt \
    busybox-extras \
    python3 py3-pip \
    curl wget ca-certificates \
    nginx \
    parted e2fsprogs dosfstools \
    iproute2 dhcpcd \
    openssh
DOCKERFILE

  docker build -f /tmp/Dockerfile.inferkern-rootfs -t inferkern-rootfs:build /tmp
  rm -f /tmp/Dockerfile.inferkern-rootfs

  # Export rootfs
  rm -rf "$OUTPUT"
  mkdir -p "$OUTPUT"
  cid=$(docker create inferkern-rootfs:build)
  docker export "$cid" | tar -x -C "$OUTPUT"
  docker rm "$cid"

elif command -v apk >/dev/null 2>&1; then
  echo "[build-rootfs] using local apk (must run as root)..."
  if [ "$(id -u)" != "0" ]; then
    echo "ERROR: local apk method requires root" >&2
    exit 1
  fi
  mkdir -p "$OUTPUT/etc/apk"
  cp /etc/apk/repositories "$OUTPUT/etc/apk/" 2>/dev/null || echo "https://dl-cdn.alpinelinux.org/alpine/v$ALPINE_VERSION/main" > "$OUTPUT/etc/apk/repositories"
  apk --root "$OUTPUT" --initdb add alpine-base linux-virt python3 nginx parted e2fsprogs

else
  echo "ERROR: need docker or apk to build rootfs" >&2
  exit 1
fi

# Overlay inferkern agent + supervisor
echo "[build-rootfs] overlaying inferkern..."
mkdir -p "$OUTPUT/app" "$OUTPUT/sbin" "$OUTPUT/etc/inferkern" "$OUTPUT/var/lib/inferkern"
cp -r "$ROOT_DIR/agent" "$OUTPUT/app/agent"
cp -r "$ROOT_DIR/checks" "$OUTPUT/app/checks"
cp -r "$ROOT_DIR/examples" "$OUTPUT/app/examples"
cp -r "$ROOT_DIR/qemu" "$OUTPUT/app/qemu"
cp "$ROOT_DIR/pyproject.toml" "$OUTPUT/app/"
cp "$ROOT_DIR/docker/entrypoint.sh" "$OUTPUT/app/" 2>/dev/null || true

# chroot pip install
if command -v docker >/dev/null 2>&1; then
  # Do it via a container with the exported rootfs
  docker run --rm -v "$OUTPUT:/rootfs" alpine:$ALPINE_VERSION sh -c \
    "apk add --no-cache python3 py3-pip && pip install --break-system-packages --root=/rootfs httpx pyyaml rich || true"
fi

# Install init wrapper as /sbin/inferkern
cp "$OUTPUT/app/qemu/init.sh" "$OUTPUT/sbin/inferkern"
chmod +x "$OUTPUT/sbin/inferkern"

# Ensure supervisor is importable from rootfs
cat > "$OUTPUT/app/setup-agent-path.sh" << 'EOF'
export PYTHONPATH="/app:$PYTHONPATH"
EOF

echo "[build-rootfs] done — rootfs at $OUTPUT"
echo "  kernel: $OUTPUT/boot/vmlinuz-virt"
echo "  init:   $OUTPUT/sbin/inferkern"
du -sh "$OUTPUT" 2>/dev/null || true
