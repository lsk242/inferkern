#!/bin/sh
# QEMU runner for Proposal B — boots Alpine rootfs with inferkern as init.
# Usage:
#   qemu/run.sh                          # use defaults (expects qemu/rootfs/ populated)
#   qemu/run.sh --disk blank.qcow2       # attach blank disk for agent to manage
#   qemu/run.sh --goal examples/goals/web-server/goal.yaml
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Defaults
ROOTFS="$ROOT_DIR/qemu/rootfs"
KERNEL="$ROOTFS/boot/vmlinuz-virt"
INITRD="$ROOTFS/boot/initramfs-virt"
GOAL_HOST=""
DISK=""
MEMORY="1024"
CPUS="2"
QEMU_BIN="${QEMU_BIN:-qemu-system-x86_64}"
EXTRA_ARGS=""

usage() {
  echo "Usage: $0 [--goal PATH] [--disk PATH] [--kernel PATH] [--initrd PATH] [--memory MB] [--cpus N] [--extra-qemu ARGS]"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --goal) GOAL_HOST="$2"; shift 2 ;;
    --disk) DISK="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initrd) INITRD="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cpus) CPUS="$2"; shift 2 ;;
    --extra-qemu) EXTRA_ARGS="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

# Check QEMU exists
if ! command -v "$QEMU_BIN" >/dev/null 2>&1; then
  echo "ERROR: $QEMU_BIN not found. Install qemu-system-x86 (apt) or qemu-system (apk)." >&2
  exit 1
fi

# Check kernel/initramfs (unless user explicitly skips)
if [ ! -f "$KERNEL" ]; then
  echo "ERROR: kernel not found at $KERNEL" >&2
  echo "  Build it first: make qemu-rootfs  (or set --kernel)" >&2
  exit 1
fi

# Build QEMU args
QEMU_ARGS="-m $MEMORY -smp $CPUS -nographic"
QEMU_ARGS="$QEMU_ARGS -kernel $KERNEL"
if [ -f "$INITRD" ]; then
  QEMU_ARGS="$QEMU_ARGS -initrd $INITRD"
fi

# Rootfs as virtio-9p share (for dev) or as disk image
if [ -d "$ROOTFS" ]; then
  QEMU_ARGS="$QEMU_ARGS -virtfs local,path=$ROOTFS,mount_tag=host-rootfs,security_model=passthrough,id=host-rootfs"
fi

# Goal file as 9p share so agent can read it
if [ -n "$GOAL_HOST" ] && [ -f "$GOAL_HOST" ]; then
  GOAL_DIR="$(cd "$(dirname "$GOAL_HOST")" && pwd)"
  QEMU_ARGS="$QEMU_ARGS -virtfs local,path=$GOAL_DIR,mount_tag=host-goal,security_model=passthrough,id=host-goal"
fi

# Blank disk for agent storage management
if [ -n "$DISK" ]; then
  if [ ! -f "$DISK" ]; then
    echo "Creating blank disk: $DISK (1G)"
    qemu-img create -f qcow2 "$DISK" 1G
  fi
  QEMU_ARGS="$QEMU_ARGS -drive file=$DISK,format=qcow2,if=virtio"
fi

# Kernel cmdline — root via 9p or disk, init is inferkern
CMDLINE="console=ttyS0 root=/dev/root rootfstype=9p rootflags=trans=virtio,version=9p2000.L init=/sbin/inferkern"
CMDLINE="$CMDLINE rw"
QEMU_ARGS="$QEMU_ARGS -append \"$CMDLINE\""

if [ -n "$EXTRA_ARGS" ]; then
  QEMU_ARGS="$QEMU_ARGS $EXTRA_ARGS"
fi

echo "[qemu] $QEMU_BIN $QEMU_ARGS" >&2
eval exec "$QEMU_BIN" $QEMU_ARGS
