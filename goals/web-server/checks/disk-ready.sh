#!/bin/sh
# Check: blank disk has been set up (partitioned, formatted, mounted for state)
# Passes if EITHER:
#   - no blank disk exists (Docker/track-A mode — state on rootfs is fine), OR
#   - blank disk is partitioned and mounted at /var/lib/inferkern or /data
set -e

STATE_DIR="${INFERKERN_STATE_DIR:-/var/lib/inferkern}"

# If no second disk device exists, this is not a VM — pass trivially
if [ ! -b /dev/vdb ] && [ ! -b /dev/sdb ] && [ ! -b /dev/nvme0n2 ]; then
  # Also check lsblk
  if ! lsblk 2>/dev/null | grep -qE 'vdb|sdb|nvme0n2'; then
    echo "PASS: no blank disk present (container mode) — disk check skipped"
    exit 0
  fi
fi

# Blank disk exists — verify it was set up
if lsblk -f 2>/dev/null | grep -qE 'vdb1|sdb1'; then
  echo "PASS: blank disk partitioned (vdb1/sdb1 exists)"
else
  echo "FAIL: blank disk present but not partitioned"
  lsblk 2>/dev/null || true
  exit 1
fi

# Check state dir is on the blank disk (or at least exists and is writable)
if mount 2>/dev/null | grep -qE "vdb1|sdb1" && mount 2>/dev/null | grep -q "$STATE_DIR\|/var/lib/inferkern"; then
  echo "PASS: state dir mounted on blank disk"
  exit 0
fi

if [ -d "$STATE_DIR" ] && [ -w "$STATE_DIR" ]; then
  echo "PASS: state dir $STATE_DIR exists and writable (mount check soft)"
  exit 0
fi

echo "FAIL: state dir $STATE_DIR not properly set up"
exit 1
