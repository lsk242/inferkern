# VM (Proposal B) — QEMU boot

Boots the Alpine rootfs with the inferkern supervisor as PID 1
(`init=/sbin/inferkern`). The supervisor mounts pseudo-filesystems,
brings up DHCP, then spawns the agent loop; the agent converges the
machine to the selected goal.

## Build + run

```bash
make vm-build            # docker-export Alpine rootfs + vmlinuz-virt
make vm-run GOAL=web-server   # QEMU, http://localhost:8080 after boot
make vm-run GOAL=smoke-test
```

Requirements: `docker` (rootfs build), `qemu-system-x86_64` + `qemu-img`
(run). Kernel is extracted from the built rootfs (`/boot/vmlinuz-virt`);
if missing, `run-qemu.sh` resolves the current `linux-virt` version from
the Alpine APKINDEX — never a pinned `.apk` URL.

## Layout

- `build-rootfs.sh` — builds `rootfs.tar` + `vmlinuz-virt` via Docker.
- `run-qemu.sh` — creates qcow2 disks, boots with user networking
  (`hostfwd 8080->80`), serial console on stdio.
- Guest init: `/sbin/inferkern` → supervisor → agent (`INFERKERN_GOAL`
  from kernel cmdline / env).
