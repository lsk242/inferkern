#!/usr/bin/env bash
# Boot the inferkern VM in QEMU.
# Supports two modes:
#   1. Direct kernel boot (-kernel/-initrd) from rootfs — fastest for dev.
#   2. Disk boot (if you bake kernel into a bootable image).
#
# Usage: scripts/run-qemu.sh [--nographic] [--port HOST_PORT] [--memory MB] [--kernel PATH] [--initrd PATH]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VM_DIR="$REPO_ROOT/vm"

# Defaults
NOGRAPHIC=false
HOST_PORT=8080
MEMORY=1024
KERNEL=""
INITRD=""
EXTRA_APPEND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --nographic) NOGRAPHIC=true; shift ;;
    --port) HOST_PORT="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    --initrd) INITRD="$2"; shift 2 ;;
    --append) EXTRA_APPEND="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [--nographic] [--port PORT] [--memory MB] [--kernel PATH] [--initrd PATH]"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Resolve kernel
if [[ -z "$KERNEL" ]]; then
  # Try rootfs kernel first
  if [[ -f "$VM_DIR/rootfs/boot/vmlinuz-virt" ]]; then
    KERNEL="$VM_DIR/rootfs/boot/vmlinuz-virt"
  elif [[ -f "$VM_DIR/vmlinuz-virt" ]]; then
    KERNEL="$VM_DIR/vmlinuz-virt"
  else
    echo "ERROR: no kernel found. Build rootfs first or pass --kernel PATH" >&2
    echo "  Expected: $VM_DIR/rootfs/boot/vmlinuz-virt" >&2
    exit 1
  fi
fi

if [[ ! -f "$KERNEL" ]]; then
  echo "ERROR: kernel not found: $KERNEL" >&2
  exit 1
fi

# Resolve initrd
if [[ -z "$INITRD" ]]; then
  for candidate in "$VM_DIR/rootfs/boot/initramfs-virt" "$VM_DIR/initramfs-virt" "$VM_DIR/rootfs/boot/initramfs-lts"; do
    if [[ -f "$candidate" ]]; then
      INITRD="$candidate"
      break
    fi
  done
fi

# Resolve rootfs dir for 9p or disk
ROOTFS_DIR="$VM_DIR/rootfs"
if [[ ! -d "$ROOTFS_DIR" ]]; then
  echo "ERROR: rootfs not found: $ROOTFS_DIR (run scripts/build-vm.sh)" >&2
  exit 1
fi

BLANK_DISK="$VM_DIR/blank.qcow2"
if [[ ! -f "$BLANK_DISK" ]]; then
  echo "WARN: blank disk not found: $BLANK_DISK — VM will boot without second disk" >&2
  BLANK_DISK=""
fi

# Goal dir as virtio-9p share (or fallback to second disk image)
GOAL_SHARE_ARGS=()
if [[ -d "$REPO_ROOT/goals" ]]; then
  GOAL_SHARE_ARGS=(-virtfs "local,path=$REPO_ROOT/goals,mount_tag=goals,security_model=passthrough,readonly=on")
fi

# Kernel cmdline
CMDLINE="console=ttyS0 console=tty0 init=/sbin/inferkern root=/dev/vda rw rootfstype=ext4"
# When using -kernel direct boot without disk, root is host-provided;
# for 9p rootfs we need different handling — use virtio-blk or 9p root.
# We provide rootfs as a disk image if available, else use -kernel with root=/dev/vda.

# Build QEMU args
QEMU_ARGS=(
  qemu-system-x86_64
  -m "$MEMORY"
  -smp 2
  -kernel "$KERNEL"
  -append "$CMDLINE $EXTRA_APPEND"
  -netdev "user,id=net0,hostfwd=tcp::${HOST_PORT}-:80"
  -device "virtio-net-pci,netdev=net0"
)

# Initrd
if [[ -n "$INITRD" ]]; then
  QEMU_ARGS+=(-initrd "$INITRD")
fi

# Rootfs: prefer a raw disk image, fall back to 9p virtio
ROOTFS_IMG="$VM_DIR/rootfs.img"
if [[ -f "$ROOTFS_IMG" ]]; then
  QEMU_ARGS+=(-drive "file=$ROOTFS_IMG,format=raw,if=virtio")
elif [[ -d "$ROOTFS_DIR" ]]; then
  # Create a minimal ext4 image from rootfs dir on the fly if possible
  # (requires root or fakeroot + mkfs.ext4)
  # For now, use 9p as root — need kernel with 9p support
  # Alpine virt kernel has CONFIG_9P_FS=y, so this works
  QEMU_ARGS+=(
    -fsdev "local,id=rootfs,path=$ROOTFS_DIR,security_model=passthrough"
    -device "virtio-9p-pci,fsdev=rootfs,mount_tag=rootfs"
  )
  # Override cmdline for 9p root
  CMDLINE="console=ttyS0 console=tty0 init=/sbin/inferkern root=rootfs rootfstype=9p rootflags=trans=virtio,version=9p2000.L rw"
  # Rebuild append
  QEMU_ARGS[5]="$CMDLINE $EXTRA_APPEND"
fi

# Blank disk (agent's playground)
if [[ -n "$BLANK_DISK" ]]; then
  QEMU_ARGS+=(-drive "file=$BLANK_DISK,format=qcow2,if=virtio")
fi

# Display
if [[ "$NOGRAPHIC" == true ]]; then
  QEMU_ARGS+=(-nographic)
else
  # Try to use available display; fall back to none if no X/Wayland
  if [[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    QEMU_ARGS+=(-nographic)
  fi
fi

echo "=== inferkern QEMU ==="
echo "  Kernel: $KERNEL"
echo "  Initrd: ${INITRD:-none}"
echo "  Rootfs: $ROOTFS_DIR"
echo "  Disk:   ${BLANK_DISK:-none}"
echo "  Memory: ${MEMORY}M"
echo "  HTTP:   http://localhost:${HOST_PORT} -> guest :80"
echo "  Cmdline: $CMDLINE $EXTRA_APPEND"
echo ""
echo "  Press Ctrl-a c then 'quit' (nographic) or close window to exit."
echo ""

# RAM warning
AVAIL_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 4096)
if (( MEMORY > AVAIL_MB - 256 )); then
  echo "WARN: requested ${MEMORY}M but host has only ${AVAIL_MB}M total — may OOM" >&2
  echo "  Try: $0 --memory 512" >&2
fi

exec "${QEMU_ARGS[@]}"
