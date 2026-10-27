# Init design: an agent loop as PID 1

How the kernel hands control to the agent, and why PID 1 itself stays dumb.

## Boot mechanics (standard Linux, no magic)

The kernel, after mounting the root filesystem, executes the init program:
`/init` on initramfs, or `/sbin/init` (overridable with the `init=` kernel
command-line parameter) on a real rootfs. If init exits or can't start, the
kernel panics. So:

- Our entrypoint is a normal binary/script at a path we pass via
  `init=/sbin/inferkern` (QEMU `-append`, GRUB `linux ... init=...`).
- It runs as PID 1: it must mount `/proc`, `/sys`, `/dev`, reap zombie
  children (or use a subreaper), and forward/handle signals. A shell script
  *can* be PID 1 but reaps poorly; a tiny supervisor binary (C/Rust/Go) or
  an existing minimal init (runit, s6, tini-style) as a parent is safer.

## The two-layer split

```
PID 1: inferkern-sup (deterministic, no LLM, ~hundreds of lines)
 └─ child: inferkern-agent (LLM-driven loop, restartable)
     └─ grandchildren: everything the agent starts (services, containers)
```

**Why not let the LLM be PID 1 directly?**

1. PID 1 must never crash, hang, or exit — an LLM call can time out, hallucinate
   an `exit`, or stall for minutes. A wedged PID 1 = dead machine.
2. Zombie reaping and signal handling are fiddly; they belong in boring code.
3. Restartability: if the agent loop corrupts its own state, the supervisor
   kills and restarts it with the persisted journal intact.
4. Rescue path: after N failures the supervisor stops restarting and drops
   to a root shell (or a minimal HTTP console) instead of kernel-panicking.

The supervisor owns: mounts, early DHCP, goal/state volume mounts, LLM
runtime startup (local server or API reachability check), agent spawn +
restart budget, rescue fallback. The agent owns: everything else.

## Agent loop pseudocode

```
load goal (/etc/inferkern/goal.md) + checks (/etc/inferkern/checks/*.sh)
load or init persistent state (/var/lib/inferkern/{facts,plan,journal}.json)
loop:
    if budget exhausted (steps, tokens, wall-clock): escalate to supervisor; halt
    observe: run discovery tools as needed (lsblk, ip, free, probes)
    if all acceptance checks pass: enter steady-state reconcile (sleep N, re-check)
    ask LLM: given goal + facts + journal tail → next action(s)
    policy gate: allowlist/denylist check; destructive ops need explicit goal sanction
    execute: run tool(s), capture exit code + before/after state
    journal: append action + result; update facts
```

## Tool surface (v1 sketch)

Safe-by-default: `read-file`, `list`, `probe` (lsblk/ip/ss/free/lspci),
`check` (run acceptance checks), `journal`. Gated: `write-file`, `exec`,
`apk/apt install`, `parted/mkfs/mount`, `service start/stop`,
`docker/podman run`. Forbidden-by-default: raw `dd` to disks hosting the
running rootfs, `mkfs` on mounted goal/state volumes, outbound network
beyond allowlisted hosts (package mirrors, LLM API), reboot/poweroff except
via supervisor request.

Borrow from SchedCP/AI-OS.NET: treat the agent as a non-cautious actor;
every destructive tool takes an explicit pre-state snapshot or dry-run diff
where feasible.

## State and idempotency

- `/var/lib/inferkern/` persists across agent restarts (and reboots, once a
  writable volume exists): facts cache, plan, append-only journal.
- Tools must be idempotent: "ensure package X installed", "ensure mount Y",
  "ensure container Z running" — re-running convergence is always safe.
- The journal is the audit trail and the debugging story: every boot's
  decisions replayable.

## Failure modes

| Failure | Handling |
| --- | --- |
| No network, no local model | Rescue state + setup helper, clear message |
| LLM API errors / rate limits | Backoff + retry budget, then rescue |
| Agent crash / exit | Supervisor restarts (bounded), journal preserved |
| Agent exceeds step/token budget | Freeze, snapshot, escalate to rescue |
| Check never passes (bad goal) | Report which check fails + last actions, stay in reconcile |
| Supervisor itself fails | Nothing left — kernel panic; keep it tiny to avoid this |

## What v1 does NOT need

Custom syscalls, kernel modules, eBPF, or a kernel patch. Stock kernel +
stock userland tools driven over fork/exec. The "kernel managed by an LLM"
is true at the control-plane level (the agent decides everything about the
running system), not at the syscall level.
