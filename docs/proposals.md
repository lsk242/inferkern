# Proposals: four build paths, compared

All four share the same agent loop and goal format; they differ in base
system and boot target. Proposed order: **A → B → C**, with D as the
standing simulation harness underneath all of them.

## Proposal A — Alpine + agent as container entrypoint (start here)

- Base: `alpine/minimal` container image.
- Boot target: Docker. The agent loop is the container's PID 1; goals like
  "become an nginx web server" execute inside the container.
- LLM: remote API (key via env).
- Effort: days. A Dockerfile, a goal file, the agent loop skeleton, checks.
- Proves: the loop, the tool surface, the goal/check format, cost per
  convergence.
- Doesn't prove: real boot, hardware discovery, partitioning, local inference.
- Exit criteria: `docker run` with a goal converges to a passing web server
  twice in a row from a clean image.

## Proposal B — Alpine mini rootfs + kernel in QEMU (first real boot)

- Base: Alpine mini rootfs + stock kernel (`apk add linux-virt` or Alpine
  virt ISO contents), custom `init=/sbin/inferkern`.
- Boot target: QEMU VM with a blank virtual disk + virtual NIC.
- New work vs A: supervisor binary (mounts, DHCP, reaping), blank-disk
  partitioning/formatting by the agent, rescue shell on failure.
- Effort: 1–3 weeks.
- Proves: the PID-1 story, hardware discovery (virtual), storage setup from
  zero, full boot→converge→serve path.
- Exit criteria: QEMU VM with blank disk boots, agent partitions, installs,
  and serves HTTP; reboot re-converges idempotently.

## Proposal C — Buildroot appliance image (the "distro" milestone)

- Base: Buildroot-generated kernel + rootfs (ISO/disk image), with or without
  a baked-in GGUF model.
- Boot target: QEMU first, then bare metal / USB stick.
- New work vs B: Buildroot config + board def, image pipeline, local
  `llama-server` integration, first-boot model fetch, offline convergence eval.
- Effort: 3–6 weeks after B.
- Proves: reproducibility, small bootable artifact, offline story.
- Exit criteria: flash/boot image on a fresh VM with no network and no API
  key → converges to goal using the local model (or cleanly reports it can't).

## Proposal D — Simulation harness (continuous, underpins A–C)

- Not a boot target: the test rig. Scripted QEMU/Docker topologies —
  blank disk, pre-partitioned disk, existing OS install, no network, slow
  network, tiny RAM — each with a goal and expected end state.
- Every agent-loop change runs against the matrix; convergence success rate
  and cost become the project's headline metrics.
- Effort: built alongside A, extended with each phase.

## Comparison

|  | A: Docker | B: QEMU/Alpine | C: Buildroot |
| --- | --- | --- | --- |
| Real kernel boot | No | Yes | Yes |
| Real storage mgmt | No | Yes (virtual) | Yes |
| Local LLM | No | Optional | Yes (goal) |
| Effort | Days | Weeks | Weeks |
| Risk | Low | Medium | Medium-high |

(D is excluded: it's the test harness running underneath A–C, not a boot target.)

## Recommendation

Approve **A immediately**; design B's supervisor interface while building A
so the agent loop doesn't need rewrites; treat C as the v1.0 definition of
"inferkern is a distro". D starts with A and never stops.
