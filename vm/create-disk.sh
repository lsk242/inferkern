#!/usr/bin/env bash
# Create a blank qcow2 virtual disk for the VM.
# The agent will partition/format/mount it idempotently on first boot.
# Usage: vm/create-disk.sh [--output PATH] [--size SIZE]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OUTPUT="${OUTPUT:-$REPO_ROOT/vm/blank.qcow2}"
SIZE="${SIZE:-2G}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --size) SIZE="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$(dirname "$OUTPUT")"

if [[ -f "$OUTPUT" ]]; then
  echo "==> Disk already exists: $OUTPUT ($(du -h "$OUTPUT" | cut -f1) on disk, virtual $SIZE)"
  echo "    Remove it first to recreate: rm $OUTPUT"
  exit 0
fi

echo "==> Creating blank qcow2 disk: $OUTPUT ($SIZE)"
qemu-img create -f qcow2 "$OUTPUT" "$SIZE"
echo "    Created: $(qemu-img info "$OUTPUT" | grep -E 'virtual size|disk size')"
echo "    Agent will partition/format this on first boot (idempotent)."
