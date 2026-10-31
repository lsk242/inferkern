#!/usr/bin/env bash
# Orchestrate VM artifact build: rootfs + disk.
# Usage: scripts/build-vm.sh [--alpine-version VER] [--disk-size SIZE] [--skip-rootfs]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VM_DIR="$REPO_ROOT/vm"

SKIP_ROOTFS=false
ALPINE_VERSION="3.20"
DISK_SIZE="2G"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alpine-version) ALPINE_VERSION="$2"; shift 2 ;;
    --disk-size) DISK_SIZE="$2"; shift 2 ;;
    --skip-rootfs) SKIP_ROOTFS=true; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

echo "=== inferkern VM build ==="
echo "  Alpine: $ALPINE_VERSION"
echo "  Disk:   $DISK_SIZE"
echo ""

if [[ "$SKIP_ROOTFS" != true ]]; then
  echo "--- Step 1: rootfs ---"
  ALPINE_VERSION="$ALPINE_VERSION" OUTPUT_DIR="$VM_DIR/rootfs" bash "$VM_DIR/build-rootfs.sh"
else
  echo "--- Step 1: rootfs (skipped) ---"
fi

echo ""
echo "--- Step 2: blank disk ---"
OUTPUT="$VM_DIR/blank.qcow2" SIZE="$DISK_SIZE" bash "$VM_DIR/create-disk.sh"

echo ""
echo "--- Step 3: verify ---"
if [[ -d "$VM_DIR/rootfs" ]]; then
  echo "  rootfs: $VM_DIR/rootfs ($(du -sh "$VM_DIR/rootfs" | cut -f1))"
  if [[ -f "$VM_DIR/rootfs/boot/vmlinuz-virt" ]]; then
    echo "  kernel: $VM_DIR/rootfs/boot/vmlinuz-virt ($(du -h "$VM_DIR/rootfs/boot/vmlinuz-virt" | cut -f1))"
  else
    echo "  kernel: NOT FOUND — provide externally or ensure apk install succeeded"
  fi
  if [[ -x "$VM_DIR/rootfs/sbin/inferkern" ]]; then
    echo "  supervisor: OK ($VM_DIR/rootfs/sbin/inferkern)"
  else
    echo "  supervisor: NOT FOUND" >&2
  fi
fi
if [[ -f "$VM_DIR/blank.qcow2" ]]; then
  echo "  disk:   $VM_DIR/blank.qcow2 ($(qemu-img info "$VM_DIR/blank.qcow2" | grep 'virtual size'))"
fi

echo ""
echo "=== Build complete ==="
echo "  Run: scripts/run-qemu.sh"
