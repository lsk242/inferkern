#!/bin/bash
# scripts/vm-demo.sh — QEMU boot demo (Proposal B)
# Requires: make vm-build already done (vm/rootfs.tar + vm/vmlinuz-virt)
# Usage:
#   ./scripts/vm-demo.sh smoke          # smoke-test in QEMU
#   ./scripts/vm-demo.sh web            # web-server in QEMU (nginx :8080)
#   ./scripts/vm-demo.sh web --kvm      # with KVM acceleration if /dev/kvm exists
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; [ -f .env ] && . .env; set +a

goal="smoke-test"
extra=""
for a in "$@"; do
  case "$a" in
    smoke) goal="smoke-test" ;;
    web) goal="web-server" ;;
    --kvm) extra="--kvm" ;;
    *) echo "Usage: $0 {smoke|web} [--kvm]"; exit 1 ;;
  esac
done

if [ ! -f vm/vmlinuz-virt ]; then
  echo "Need VM kernel — run: make vm-build  (or ./scripts/setup.sh)"
  exit 1
fi
if [ ! -f vm/rootfs.tar ]; then
  echo "Need VM rootfs — run: make vm-build"
  exit 1
fi

echo "== QEMU boot: goal=$goal =="
echo "Kernel: $(du -h vm/vmlinuz-virt | cut -f1), Rootfs: $(du -h vm/rootfs.tar | cut -f1)"
echo "Serial is stdio; QEMU forwards 8080->80, 8765->8765"
echo "Exit QEMU: Ctrl-a c then 'quit'  (or poweroff inside VM)"
echo ""
bash vm/run-qemu.sh --goal "$goal" $extra
