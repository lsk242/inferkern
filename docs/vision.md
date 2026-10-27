# Vision

## One-liner

A Linux distribution consisting of a kernel plus an LLM-driven agent loop
as init. The system has no fixed personality at boot — it converges into
one, driven by a declared goal.

## Problem

Installing and operating a Linux server is a long tail of small decisions:
partition layout, filesystem, network config, packages, services, hardening,
containers. Existing automation (cloud-init, Ansible, NixOS) is static:
it executes a plan written for hardware the author imagined. When reality
differs — an extra disk, a missing NIC driver, an existing install — the
plan breaks and a human debugs.

## Idea

Replace the static plan with a reasoning loop. The kernel boots and starts
an agent as PID 1. The agent:

1. **Discovers** — enumerate block devices, network interfaces, memory, CPU,
   existing partitions and OS installs, virtualization/container context.
2. **Reasons** — compare observed state against the declared goal
   (`/etc/inferkern/goal.md`) and produce next actions.
3. **Acts** — run commands, write files, partition/format/mount, install
   packages, start supervised services, run containers.
4. **Verifies** — check that each action had the intended effect; roll back
   or retry on failure.
5. **Converges** — repeat until the goal's acceptance checks pass, then
   switch to a steady-state reconcile loop (like Kubernetes for one machine).

## Architecture sketch

```
┌─────────────────────────────────────────────────────────┐
│  Boot: kernel → init=/sbin/inferkern (PID 1)            │
├─────────────────────────────────────────────────────────┤
│  inferkern init (small, deterministic, non-LLM)         │
│  - mount /proc /sys /dev, basic networking (DHCP)       │
│  - mount goal + state volumes                           │
│  - start LLM runtime (local GGUF server or remote API)  │
│  - spawn agent loop, supervise + restart it             │
│  - fallback: drop to rescue shell if agent fails N×     │
├─────────────────────────────────────────────────────────┤
│  Agent loop (LLM-driven)                                │
│  - tools: exec, read/write files, parted/mkfs/mount,    │
│    apk/apt, ip/nm, docker/podman, systemd-less procd    │
│  - policy: allowlist + denylist, dry-run diffs, budget  │
│  - memory: /var/lib/inferkern/state (journal + facts)   │
├─────────────────────────────────────────────────────────┤
│  Goal: /etc/inferkern/goal.md + checks/*.sh             │
└─────────────────────────────────────────────────────────┘
```

Key split: **PID 1 itself is dumb and deterministic.** The LLM drives a
child loop that PID 1 supervises. This keeps boot reliable (a confused
model must never wedge init) and gives us a clean restart/rescue story.
See [init design](research/init-design.md).

## Design principles

1. **Converge, don't install.** Every boot reconciles current state with
   the goal. Re-running is always safe (idempotent tools).
2. **Boring base, smart top.** Reuse a stock kernel and a minimal userland.
   Novelty lives in the agent loop, not in forked infrastructure.
3. **Evidence over assertion.** Every action is journaled with before/after
   state; acceptance checks decide "done", not the model's confidence.
4. **Degrade gracefully.** No network? No API key? No GPU? The agent must
   still reach a useful rescue state and explain what it needs.
5. **Simulate first.** Every milestone must run in Docker, then QEMU, before
   touching bare metal.

## Non-goals (for now)

- A desktop environment.
- A custom kernel fork or custom syscalls.
- Replacing the LLM ecosystem — we consume models via APIs and GGUF
  runtimes, we don't train or serve novel ones.
- Multi-node orchestration (single-machine converge first; fleet later, if ever).
