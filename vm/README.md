# VM artifacts

| File | Purpose |
|------|---------|
| `build-rootfs.sh` | Fetch Alpine mini-rootfs tarball, install `linux-virt` + supervisor + agent into `vm/rootfs/` |
| `create-disk.sh` | `qemu-img create` blank qcow2 for agent to partition/format |
| `rootfs/` | Built rootfs (gitignored, generated) |
| `blank.qcow2` | Blank disk (gitignored, generated) |
| `rootfs.img` | Optional raw disk image (if you convert rootfs to ext4 image) |

Kernel: `vm/rootfs/boot/vmlinuz-virt` (from `apk add linux-virt`). If `apk` is not
available on the host, build inside Docker:

```bash
docker run --rm -v $PWD:/work -w /work alpine:3.20 sh -c 'apk add bash curl && vm/build-rootfs.sh'
```

RAM note: host has ~3.3 GiB. Use `scripts/run-qemu.sh --memory 512` to stay safe.
