# QEMU target (Proposal B)

## Prerequisites

```bash
# Debian/Ubuntu
sudo apt install qemu-system-x86 qemu-utils

# Alpine
apk add qemu-system-x86_64 qemu-img
```

## Build the Alpine rootfs

```bash
make qemu-rootfs
# Produces qemu/rootfs/ with Alpine mini + kernel + inferkern agent
```

This requires `docker` (builds rootfs inside an Alpine container) or a local
Alpine host with `apk` available. See `qemu/build-rootfs.sh`.

## Boot in QEMU

```bash
# Boot with default web-server goal
qemu/run.sh

# With a blank disk for the agent to partition/format
qemu/run.sh --disk /tmp/inferkern-disk.qcow2

# Custom goal
qemu/run.sh --goal examples/goals/web-server/goal.llm.yaml --disk /tmp/disk.qcow2

# Extra QEMU args (e.g. host networking)
qemu/run.sh --extra-qemu "-netdev user,id=net0,hostfwd=tcp::8080-:80 -device virtio-net-pci,netdev=net0"
```

## What happens at boot

1. Kernel boots, `init=/sbin/inferkern` (our `qemu/init.sh` → `qemu/supervisor.py`)
2. Supervisor mounts pseudofs, brings up network, mounts goal/state volumes
3. Agent loop starts, discovers hardware (virtual disks, NICs), converges toward goal
4. On success: steady-state reconcile loop; on failure: bounded restarts → rescue shell
