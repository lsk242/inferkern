#!/usr/bin/env bash
# Build Alpine mini-rootfs for inferkern VM.
# Fetch Alpine mini root filesystem tarball, unpack, install kernel + supervisor + agent.
# Usage: vm/build-rootfs.sh [--output DIR] [--alpine-version VER]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/vm/rootfs}"
ALPINE_VERSION="${ALPINE_VERSION:-3.20}"
ALPINE_ARCH="x86_64"
MIRROR="https://dl-cdn.alpinelinux.org/alpine"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --alpine-version) ALPINE_VERSION="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

echo "==> Building Alpine rootfs v${ALPINE_VERSION} -> ${OUTPUT_DIR}"

# Check if we can run without root (fakeroot or real root preferred)
if [[ $EUID -ne 0 ]] && ! command -v fakeroot &>/dev/null; then
  echo "WARN: not root and fakeroot not found; file ownership may be wrong" >&2
  echo "      install fakeroot or run with sudo for correct image" >&2
fi

TARBALL_URL="${MIRROR}/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/alpine-minirootfs-${ALPINE_VERSION}.0-${ALPINE_ARCH}.tar.gz"
# Fallback: try without .0 patch
TMPDIR="$(mktemp -d)"
TARBALL="$TMPDIR/minirootfs.tar.gz"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

echo "==> Downloading $TARBALL_URL"
if ! curl -fsSL -o "$TARBALL" "$TARBALL_URL"; then
  # Try alternate URL patterns
  for suffix in "" ".1" ".2" ".3"; do
    ALT_URL="${MIRROR}/v${ALPINE_VERSION}/releases/${ALPINE_ARCH}/alpine-minirootfs-${ALPINE_VERSION}${suffix}-${ALPINE_ARCH}.tar.gz"
    echo "    trying $ALT_URL"
    if curl -fsSL -o "$TARBALL" "$ALT_URL"; then
      echo "    got $ALT_URL"
      break
    fi
  done
fi

if [[ ! -s "$TARBALL" ]]; then
  echo "ERROR: failed to download Alpine minirootfs tarball" >&2
  echo "  Tried: $TARBALL_URL (and variants)" >&2
  exit 1
fi

echo "==> Extracting to $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
tar -xzf "$TARBALL" -C "$OUTPUT_DIR"

# --------------------------------------------------------------------------
# Install packages inside rootfs (requires chroot or apk --root)
# --------------------------------------------------------------------------

# Write apk mirror
mkdir -p "$OUTPUT_DIR/etc/apk"
echo "${MIRROR}/v${ALPINE_VERSION}/main" > "$OUTPUT_DIR/etc/apk/repositories"
echo "${MIRROR}/v${ALPINE_VERSION}/community" >> "$OUTPUT_DIR/etc/apk/repositories"

# Mount pseudo-fs for apk
mount_chroot() {
  mount --bind /dev "$OUTPUT_DIR/dev" 2>/dev/null || true
  mount -t proc proc "$OUTPUT_DIR/proc" 2>/dev/null || true
  mount -t sysfs sysfs "$OUTPUT_DIR/sys" 2>/dev/null || true
}

umount_chroot() {
  umount "$OUTPUT_DIR/proc" 2>/dev/null || true
  umount "$OUTPUT_DIR/sys" 2>/dev/null || true
  umount "$OUTPUT_DIR/dev" 2>/dev/null || true
}

# Try apk --root first (works without chroot on Debian if apk-tools-static available)
install_pkgs() {
  local pkgs=(
    linux-virt virt-kernel-config
    alpine-base busybox-openrc openrc
    python3 py3-pip
    nginx curl ca-certificates
    parted e2fsprogs dosfstools lsblk
    iproute2 iputils
    tini
  )
  echo "==> Installing packages: ${pkgs[*]}"

  if command -v apk &>/dev/null; then
    # apk --root works even without chroot if apk-tools is installed
    mount_chroot
    # --allow-untrusted for cross-distro use; keys are in tarball's /etc/apk/keys
    if apk --root "$OUTPUT_DIR" --no-cache add "${pkgs[@]}" 2>&1; then
      echo "    apk --root succeeded"
    else
      echo "WARN: apk --root had errors (some pkgs may be missing)" >&2
      # Non-fatal — supervisor+agent are the critical pieces
    fi
    umount_chroot
  else
    echo "WARN: apk not found on host; skipping in-rootfs package install" >&2
    echo "  On Debian/Ubuntu: apt install apk-tools (or build inside Docker: docker run --rm -v \$PWD:/work alpine:3.20 sh -c '...')" >&2
    echo "  Kernel + packages must be installed separately or via Docker builder" >&2
  fi
}

install_pkgs

# --------------------------------------------------------------------------
# Install supervisor + agent into rootfs
# --------------------------------------------------------------------------

echo "==> Installing inferkern supervisor"
mkdir -p "$OUTPUT_DIR/sbin"
mkdir -p "$OUTPUT_DIR/usr/lib/inferkern"
cp "$REPO_ROOT/supervisor/sup.py" "$OUTPUT_DIR/sbin/inferkern"
chmod +x "$OUTPUT_DIR/sbin/inferkern"

# Agent (if present from track A)
if [[ -d "$REPO_ROOT/agent" ]]; then
  echo "==> Installing agent from agent/"
  cp -r "$REPO_ROOT/agent" "$OUTPUT_DIR/usr/lib/inferkern/agent"
  # Ensure agent deps
  if [[ -f "$REPO_ROOT/agent/requirements.txt" ]]; then
    echo "    (agent requirements.txt present — pip install at runtime or bake via Docker)"
  fi
else
  echo "WARN: agent/ not found — VM will boot supervisor only" >&2
  mkdir -p "$OUTPUT_DIR/usr/lib/inferkern/agent"
  cat > "$OUTPUT_DIR/usr/lib/inferkern/agent/__main__.py" <<'PYEOF'
"""Placeholder agent — replace with real agent/ from track A."""
import time, sys
print("[agent] placeholder agent running (no real agent installed)", flush=True)
# Simulate work then exit 0
time.sleep(2)
print("[agent] placeholder done", flush=True)
sys.exit(0)
PYEOF
fi

# Goals
if [[ -d "$REPO_ROOT/goals" ]]; then
  echo "==> Installing goals"
  mkdir -p "$OUTPUT_DIR/etc/inferkern"
  cp -r "$REPO_ROOT/goals" "$OUTPUT_DIR/etc/inferkern/goals"
  # Default goal symlink
  if [[ -d "$OUTPUT_DIR/etc/inferkern/goals/web-server" ]]; then
    ln -sf goals/web-server/goal.md "$OUTPUT_DIR/etc/inferkern/goal.md" 2>/dev/null || true
  fi
fi

# State dir (will be backed by blank disk partition once agent sets it up)
mkdir -p "$OUTPUT_DIR/var/lib/inferkern"

# Ensure /etc/inferkern exists
mkdir -p "$OUTPUT_DIR/etc/inferkern"

# --------------------------------------------------------------------------
# Kernel / initramfs notes
# --------------------------------------------------------------------------

# Alpine's linux-virt installs kernel to /boot/vmlinuz-virt
if [[ -f "$OUTPUT_DIR/boot/vmlinuz-virt" ]]; then
  echo "==> Kernel found: $OUTPUT_DIR/boot/vmlinuz-virt"
  # Also copy initramfs if present
  if [[ -f "$OUTPUT_DIR/boot/initramfs-virt" ]]; then
    echo "    initramfs: $OUTPUT_DIR/boot/initramfs-virt"
  fi
else
  echo "WARN: no kernel at $OUTPUT_DIR/boot/vmlinuz-virt" >&2
  echo "  Provide kernel via: apk add linux-virt (inside rootfs) or external build" >&2
fi

# Make sure /sbin/inferkern is executable and has correct shebang
chmod +x "$OUTPUT_DIR/sbin/inferkern"

echo "==> Rootfs ready at $OUTPUT_DIR"
echo "    Kernel:  $OUTPUT_DIR/boot/vmlinuz-virt (or provide externally)"
echo "    Init:    /sbin/inferkern"
echo "    Size:    $(du -sh "$OUTPUT_DIR" | cut -f1)"
