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
