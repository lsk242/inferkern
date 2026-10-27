# Base options: what the kernel boots into

Question: Linux From Scratch, or a stripped-down minimal distro (Alpine,
Debian/Ubuntu minimal)? Plus the appliance builders: Buildroot, Yocto.

**Recommendation: Alpine minimal first** (small, fast, apk is scriptable),
with Debian netinst as the glibc fallback. Prove the agent-init loop in
Docker + QEMU. Consider Buildroot only for a later from-source appliance.
Avoid LFS and Yocto for v1.

## Option 1 — Linux From Scratch (LFS)

Build the entire userland from source, by hand, following the LFS book.

- Pros: total control; smallest possible system; deep understanding of every
  component; no distro opinions to fight.
- Cons: enormous time cost; every security update is manual recompilation;
  no package manager (that's BLFS territory, even more work); reproducibility
  depends on our own scripts; a one-person maintenance burden forever.
- Verdict: **reject for v1**. Revisit only if the project ever needs a
  pedagogical "no upstream" story. LFS is a book, not a base.

## Option 2 — Alpine Linux minimal (recommended)

Base install ~5–10 MB; musl libc + BusyBox; OpenRC (which we would bypass
with our own init anyway); `apk` package manager with a large repo.

- Pros: the smallest maintained base; fast boot; `apk` is simple and
  scriptable (great for an agent); huge container ecosystem means most
  server software is one `apk add` away; security-minded upstream;
  runs identically in Docker and QEMU (Alpine virt images exist).
- Cons: musl vs glibc — some prebuilt binaries (notably some LLM runtimes
  and proprietary blobs) assume glibc. Workarounds exist (gcompat, static
  builds) but need validation per component. OpenRC knowledge doesn't
  transfer if we replace init (fine — replacing init is the point).
- Verdict: **default base for v1.** If a critical component needs glibc,
  fall back to Option 3 rather than fighting musl.

## Option 3 — Debian netinst minimal / Ubuntu Server minimal

Debian netinstall without tasksel, or Ubuntu Server minimized. glibc,
systemd present but replaceable via `init=` kernel parameter, `apt` with
the largest package archive.

- Pros: glibc compatibility (everything runs); largest package set; familiar
  to most operators; long support windows (Debian LTS, Ubuntu LTS).
- Cons: much heavier starting point (hundreds of MB even minimized);
  stripping a Debian system down without breaking `apt` dependency chains
  is fiddly; slower boot; systemd-isms leak into many packages' assumptions.
- Verdict: **glibc fallback.** Also the likely base for the "container host"
  goal if Docker + GPU + vendor drivers fight musl.

## Option 4 — Buildroot (appliance builder)

Menuconfig-driven cross-compilation system that emits a kernel + rootfs
image (ISO, ext4, initramfs) from pinned sources. Output is firmware-like:
no on-device package manager by default.

- Pros: minimal, reproducible, fast-booting images purpose-built for the
  task; large recipe collection; much simpler than Yocto; ideal "phase 2"
  target for a true inferkern appliance image.
- Cons: no runtime package manager means the agent can't `apk add`/`apt
  install` its way out of surprises — every capability must be baked in or
  fetched as static binaries/containers. Slower iteration than Alpine
  (rebuild image per change). Learning curve moderate.
- Verdict: **phase 2 candidate** for the "real distro image" milestone.
  Not v1 — v1 needs package-manager flexibility while the agent's needs
  are still unknown.

## Option 5 — Yocto / OpenEmbedded

Full distro-construction framework: layers, BitBake recipes, BSP support,
package feeds, long-term maintenance story.

- Pros: the industrial answer for "ship a maintained custom distro across
  hardware variants"; package-based updates; vendor BSP ecosystem.
- Cons: very steep learning curve; heavy build infra; overkill for a
  fixed-function prototype; slow iteration.
- Verdict: **reject for v1/v2.** Only if inferkern ever becomes a
  multi-hardware product line.

## Reference worth stealing from regardless

- **Minimal Linux Live** (github.com/ivandavidov/minimal): shell-script-built
  micro distro with a readable custom init and ISO/USB output. Even if we
  base on Alpine, its init scripts and image-assembly approach are the best
  worked example of "kernel → custom init → usable shell" in ~hundreds of
  lines.

## Suggested path

```
Phase 0 (now)     Docker: Alpine + agent loop as container entrypoint
Phase 1           QEMU: Alpine mini rootfs + kernel, init=/sbin/inferkern
Phase 2           QEMU: same, but Buildroot-built rootfs (appliance image)
Phase 3           Bare metal / real VM ISP-style install
```

Each phase keeps the agent loop identical; only the base and the boot
mechanism change. The Dockerfile/QEMU scripts from early phases become the
regression harness for later ones.
