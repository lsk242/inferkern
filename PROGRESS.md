# Progress

Running log for inferkern. Newest entries at the bottom.

## 2026-10-27 — Repo initialized, research phase complete

- Initialized docs scaffold: README (tagline: "The Linux distro where PID 1
  is an LLM agent loop"), vision, roadmap, progress log.
- Prior-art survey done (`docs/research/prior-art.md`):
  - No exact match found for "LLM agent loop as Linux init".
  - Closest: AI-OS.NET (governed AI-native distro, boots in QEMU),
    OpenDAN (LLM-kernel personal server), AIOS (academic agent-OS),
    Osiris (Arch + agent desktop), openKylin, Anolis OS 27, Debian-AI
    proposal, SchedCP (safe kernel-agent interface), OpenClaw (product
    reference for agent-operated machines).
- Base decision (`docs/research/base-options.md`): Alpine minimal first,
  Debian netinst as glibc fallback; Buildroot for the later appliance
  phase; LFS/Yocto rejected for v1.
- LLM runtime (`docs/research/llm-runtime.md`): remote API first for dev,
  local GGUF via llama-server for the offline story; staged fallback with
  rescue state.
- Init design (`docs/research/init-design.md`): deterministic supervisor as
  PID 1, LLM agent as supervised child; tool allowlist, journal, budgets.
- Proposals A–D (`docs/proposals.md`): Docker → QEMU/Alpine →
  Buildroot appliance + standing simulation harness.
- Use cases (`docs/use-cases.md`): web server → container host →
  OpenClaw-style assistant node; draft goal/check file format.
- Next: pick agent-loop language + first LLM API, then start Phase 1
  (Proposal A in Docker).

## 2026-11-04 — Full review + consolidated Docker/VM implementation

- Reviewed all 16 open PRs (#1, #2, #3, #4, #17–#28):
  `docs/review-all-open-prs.md`. Decision: #1 as base, salvage
  Config/logging/tini/tests from #2 and CI from #4, close the rest as
  superseded (recipe goals verified byte-identical to consolidated).
- Applied #1 review fixes: supervisor `__init__` duplication, dead
  reaper, exact policy matching (+decoy test), APKINDEX kernel
  resolution, `pgrep -x` service check, SIGTERM-aware keep-alive.
- Verified: pytest 18 passed (in-image); local + Docker smoke converge;
  Docker web-server (nginx) exit 0; detached :8080 HTTP 200; graceful
  stop 0.5s; harness 2/2; VM rootfs 132M + vmlinuz-virt 11M built.
  QEMU boot pending a host with qemu-system-x86_64.
