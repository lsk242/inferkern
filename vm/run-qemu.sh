#!/bin/bash
# vm/run-qemu.sh — Boot the Alpine rootfs with inferkern as init in QEMU.
# Requires: qemu-system-x86_64, kernel+initramfs or ability to boot from disk image.
# Two modes:
#   1) kernel boot: needs vm/vmlinuz + vm/initramfs (built from Alpine)
#   2) disk boot: builds a qcow2 from vm/rootfs/ and boots it
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
GOAL="web-server"
DISK_IMG="$SCRIPT_DIR/disk.qcow2"
STATE_IMG="$SCRIPT_DIR/state.qcow2"
ROOTFS="$SCRIPT_DIR/rootfs"
TARBALL="$SCRIPT_DIR/rootfs.tar"

while [ $# -gt 0 ]; do
  case "$1" in
    --goal) GOAL="$2"; shift 2;;
    --disk) DISK_IMG="$2"; shift 2;;
    --rootfs) ROOTFS="$2"; shift 2;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done

echo "[vm/run-qemu] goal=$GOAL"

# Find QEMU
QEMU=""
for q in qemu-system-x86_64 qemu-system-x86 qemu-kvm; do
  if command -v "$q" >/dev/null 2>&1; then QEMU="$q"; break; fi
done
if [ -z "$QEMU" ]; then
  echo "error: qemu-system-x86_64 not found" >&2
  echo "install: sudo apt-get install -y qemu-system-x86 qemu-utils" >&2
  exit 1
fi
echo " -> QEMU: $QEMU ($($QEMU --version | head -1))"

# Ensure we have a rootfs
if [ ! -d "$ROOTFS" ] || [ -z "$(ls -A "$ROOTFS" 2>/dev/null)" ]; then
  if [ -f "$TARBALL" ]; then
    echo " -> extracting $TARBALL to $ROOTFS"
    mkdir -p "$ROOTFS"
    tar -xf "$TARBALL" -C "$ROOTFS"
  else
    echo "error: no rootfs at $ROOTFS and no $TARBALL" >&2
    echo "hint: run 'make vm-build' first" >&2
    exit 1
  fi
fi

# Check for prebuilt Alpine kernel/initramfs — otherwise fetch Alpine virt kernel
KERNEL="$SCRIPT_DIR/vmlinuz-virt"
INITRAMFS="$SCRIPT_DIR/initramfs-virt"
if [ ! -f "$KERNEL" ] || [ ! -f "$INITRAMFS" ]; then
  echo " -> kernel/initramfs not found, will attempt to extract from Alpine"
  # Try to get kernel from Alpine apk inside rootfs
  if [ -f "$ROOTFS/boot/vmlinuz-virt" ]; then
    cp "$ROOTFS/boot/vmlinuz-virt" "$KERNEL"
    echo "    found kernel in rootfs/boot"
  elif [ -f "$ROOTFS/boot/vmlinuz-lts" ]; then
    cp "$ROOTFS/boot/vmlinuz-lts" "$KERNEL"
    echo "    found kernel lts in rootfs/boot"
  else
    # Fetch Alpine mini rootfs style: download kernel package
    echo "    fetching Alpine virt kernel (~15 MB)..."
    TMPD=$(mktemp -d)
    ARCH="x86_64"
    # Alpine 3.20 virt kernel
    KURL="https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64/linux-virt-6.6.63-r0.apk"
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$KURL" -o "$TMPD/linux-virt.apk" 2>&1 || wget -q "$KURL" -O "$TMPD/linux-virt.apk" 2>&1 || echo "download failed, trying alternate"
    else
      wget -q "$KURL" -O "$TMPD/linux-virt.apk" 2>&1 || true
    fi
    if [ -f "$TMPD/linux-virt.apk" ]; then
      tar -xzf "$TMPD/linux-virt.apk" -C "$TMPD" 2>/dev/null || tar -xf "$TMPD/linux-virt.apk" -C "$TMPD" 2>/dev/null || true
      find "$TMPD" -name "vmlinuz*" | head -1 | xargs -I{} cp {} "$KERNEL" 2>/dev/null || true
      rm -rf "$TMPD"
    fi
    if [ ! -f "$KERNEL" ]; then
      echo "warning: could not fetch kernel — building disk image fallback instead"
      KERNEL=""
    fi
  fi
  # initramfs is optional — we can boot with rootfs as disk
fi

# Build disk images
echo " -> building disk images"

# State disk (second disk, ext4, blank — supervisor will format/mount if needed)
if [ ! -f "$STATE_IMG" ]; then
  echo "    creating state disk 512M"
  qemu-img create -f qcow2 "$STATE_IMG" 512M 2>&1 | tail -3
fi

# Root disk from rootfs
if [ ! -f "$DISK_IMG" ]; then
  echo "    creating root disk from $ROOTFS (this may take a minute)..."
  # Create ext4 image, copy rootfs in
  # Use virt-make-fs if available, else manual via loop mount or guestfish
  if command -v virt-make-fs >/dev/null 2>&1; then
    virt-make-fs --type=ext4 --size=+200M "$ROOTFS" "$DISK_IMG" 2>&1 | tail -5
    qemu-img convert -f raw -O qcow2 "$DISK_IMG" "${DISK_IMG}.qcow2" 2>/dev/null && mv "${DISK_IMG}.qcow2" "$DISK_IMG" || true
  else
    # Fallback: create raw ext4 image and copy via debugfs or tar-in-image
    # We'll create a raw ext4 and use guestfish if available, else loop mount with sudo if possible
    TMP_RAW="$SCRIPT_DIR/root.raw"
    # Estimate size: rootfs size + 300M slack
    SZ_MB=$(du -sm "$ROOTFS" | cut -f1)
    SZ_MB=$((SZ_MB + 500))
    echo "    creating ${SZ_MB}M raw image at $TMP_RAW"
    truncate -s "${SZ_MB}M" "$TMP_RAW"
    mkfs.ext4 -F "$TMP_RAW" 2>&1 | tail -3
    # Try to populate
    if command -v guestfish >/dev/null 2>&1; then
      echo "    populating via guestfish"
      guestfish --rw -a "$TMP_RAW" <<GUESTFISH
run
mount /dev/sda /
tar-in $TARBALL /
GUESTFISH
    else
      # Try loop mount (needs sudo or user namespace)
      MNT=$(mktemp -d)
      if sudo mount -o loop "$TMP_RAW" "$MNT" 2>/dev/null; then
        echo "    populating via loop mount (sudo)"
        sudo tar -xf "$TARBALL" -C "$MNT" 2>&1 | tail -5
        sudo umount "$MNT"
        sudo chown -R "$(id -u):$(id -g)" "$TMP_RAW" 2>/dev/null || true
      else
        # Last resort: manual via debugfs write (slow but works without privileges)
        echo "    warning: no guestfish/sudo — using e2cp fallback (may be slow)"
        # For now, create tarball-based initramfs path and rely on kernel+initramfs boot instead
        rm -f "$TMP_RAW"
        echo "    hint: install libguestfs-tools for disk creation: sudo apt-get install -y libguestfs-tools"
      fi
      rmdir "$MNT" 2>/dev/null || true
    fi
    if [ -f "$TMP_RAW" ]; then
      qemu-img convert -f raw -O qcow2 "$TMP_RAW" "$DISK_IMG" 2>&1 | tail -3
      rm -f "$TMP_RAW"
    fi
  fi
fi

if [ ! -f "$DISK_IMG" ]; then
  echo "error: failed to create $DISK_IMG — see hints above" >&2
  exit 1
fi

echo " -> disk: $DISK_IMG ($(du -sh "$DISK_IMG" 2>/dev/null | cut -f1))"
echo " -> state: $STATE_IMG ($(du -sh "$STATE_IMG" 2>/dev/null | cut -f1))"

# Kernel cmdline
CMDLINE="console=ttyS0,115200 console=tty0 root=/dev/vda rw init=/usr/local/bin/inferkern-init panic=1 INFERKERN_GOAL=/goals/$GOAL/goal.yaml INFERKERN_STATE_DIR=/var/lib/inferkern"
# Allow LLM passthrough for QEMU demo (user can export before make vm-run)
if [ -n "${INFERKERN_LLM_ENDPOINT:-}" ]; then
  CMDLINE="$CMDLINE INFERKERN_LLM_ENDPOINT=$INFERKERN_LLM_ENDPOINT"
fi

# Also inject via qemu -append and via kernel env
echo " -> cmdline: $CMDLINE"

# Run QEMU
# Networking: user-mode with host forward 8080->80
# Serial: stdio + file log
LOG="$SCRIPT_DIR/qemu.log"
echo "[vm/run-qemu] starting QEMU — log: $LOG  http://localhost:8080/ after boot"
echo "[vm/run-qemu] (Ctrl-a c then 'quit' or 'poweroff' inside VM to exit)"

# Prefer kernel boot if we have it, else try direct disk boot (needs bootloader on disk)
QEMU_ARGS=(
  -m 1024
  -smp 2
  -netdev user,id=net0,hostfwd=tcp::8080-:80
  -device virtio-net-pci,netdev=net0
  -drive if=virtio,format=qcow2,file="$DISK_IMG"
  -drive if=virtio,format=qcow2,file="$STATE_IMG"
  -serial mon:stdio
  -nographic
  -no-reboot
)

if [ -n "${KERNEL:-}" ] && [ -f "$KERNEL" ]; then
  QEMU_ARGS+=(-kernel "$KERNEL" -append "$CMDLINE")
  if [ -f "$INITRAMFS" ]; then
    QEMU_ARGS+=(-initrd "$INITRAMFS")
  fi
else
  # Disk boot — relies on bootloader (syslinux) on disk; if none, this will fail with guidance
  if [ ! -f "$DISK_IMG" ]; then
    echo "error: need either kernel+initramfs or bootable disk" >&2
    exit 1
  fi
fi

# Allow extra QEMU args via env
if [ -n "${QEMU_EXTRA_ARGS:-}" ]; then
  # shellcheck disable=SC2086
  QEMU_ARGS+=($QEMU_EXTRA_ARGS)
fi

set -x
exec $QEMU "${QEMU_ARGS[@]}" 2>&1 | tee "$LOG"
