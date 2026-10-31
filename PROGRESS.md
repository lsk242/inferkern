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

## 2026-10-31 — Proposals A & B implemented

- **Agent loop** (`agent/`): goal parser (YAML + front-matter + env expansion),
  tool registry (`exec`, `read_file`, `write_file`, `list_dir`, `check`, `probe`),
  LLM providers (OpenAI-compatible, Anthropic, mock), journal/state persistence,
  policy allowlist/denylist gate, budget tracker (steps/tokens/wall-clock),
  convergence loop with steady-state reconcile.
- **Proposal A — Docker** (`docker/`): `alpine:3.20` image, agent as container
  entrypoint, bundled mock web-server goal that converges to nginx on :80 with no
  API key. LLM goal variant (`goal.llm.yaml`) for real API usage.
- **Proposal B — QEMU** (`qemu/`): deterministic supervisor (`inferkern-sup`) —
  mounts, DHCP, goal/state volume mounts, SIGCHLD reaping, bounded restarts,
  rescue shell; `init.sh` wrapper for `init=` cmdline; `run.sh` QEMU launcher;
  `build-rootfs.sh` for Alpine mini rootfs (via Docker or local apk).
- **Checks** (`checks/`): `http-200.sh`, `service-persists.sh`, `content-served.sh`
  — shell scripts returning 0/1, shared by agent and harness.
- **Harness** (`harness/run.py`): rerun-from-clean × N with success rate + timing,
  JSON output.
- **CI** (`.github/workflows/ci.yml`): pytest + ruff + Docker smoke (dry-run + mock
  convergence).
- **Project files**: `pyproject.toml`, `Makefile`, `.gitignore`, 28 tests.
- Next: Proposal C (Buildroot appliance), local GGUF inference, bare-metal boot.
