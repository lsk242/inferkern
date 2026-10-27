# Roadmap

Phases map to [proposals](proposals.md). Each phase ends with a demo + a
harness regression run. Dates are TBD — this is a side project until Phase 1
lands.

## Phase 0 — Research & docs (current)

- [x] Prior-art survey ([prior art](research/prior-art.md))
- [x] Base decision: Alpine first ([base options](research/base-options.md))
- [x] LLM runtime options ([llm runtime](research/llm-runtime.md))
- [x] Init/supervisor design ([init design](research/init-design.md))
- [x] Proposals A–D ([proposals](proposals.md))
- [x] First goals: web server → container host → assistant node
      ([use cases](use-cases.md))
- [x] Pick agent-loop implementation language → **Python** (decided 2026-10-27)
- [ ] Pick first remote LLM API + budget caps

## Phase 1 — Proposal A: Dockerized agent loop

- Agent loop skeleton: goal parser, tool registry (exec, read/write, apk,
  service), journal, policy gate.
- Goal: `web-server` (nginx on Alpine, checks pass).
- LLM via remote API; step/token budgets enforced.
- Demo: `docker build && docker run` converges blank Alpine → serving HTTP.
- Harness v0: rerun-from-clean × N, record success rate + cost.

## Phase 2 — Proposal B: real boot in QEMU

- Supervisor binary (`inferkern-sup`): mounts, DHCP, reaping, agent spawn +
  restart budget, rescue shell.
- Alpine mini rootfs + stock kernel, `init=/sbin/inferkern`.
- Blank virtual disk: agent partitions, formats, mounts.
- Goal: `web-server`, then `container-host`.
- Demo: `qemu-system-x86_64` boots blank disk → serves HTTP; reboot
  re-converges with no human input.

## Phase 3 — Proposal C: appliance image

- Buildroot config emitting a bootable inferkern image (ISO + disk).
- Local inference path: bundled or first-boot-fetched GGUF + `llama-server`.
- Offline convergence eval (success rate local vs remote LLM).
- Bare-metal boot on at least one real machine (or USB stick on a laptop).
- Demo: unplug network, boot, converge (or cleanly explain why it can't).

## Phase 4 — Assistant node + hardening

- Goal: `assistant-node` (self-hosted agent à la OpenClaw, configured from
  a goal file + injected secrets).
- Secret story: sealed/TPM/cloud-init-style injection, no keys in cmdline.
- Policy hardening: typed actions, dry-run diffs, audit journal export.
- Cost/latency optimization; small-model evals for offline mode.

## Out of scope (parked)

Desktop, custom kernel fork, multi-node fleet, training our own models.
See [vision](vision.md#non-goals-for-now).
