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

## 2026-10-31 — Phase 1 + 2 scaffold: Docker + VM demo ready
- Reviewed theory/proposals; captured gaps + decisions in `docs/review-2026-10-31.md`.
  Key fix: goal format is now `goal.yaml` (pure YAML, validated), not markdown+YAML hybrid.
- Decisions: Python 3.11+ for agent/supervisor; OpenAI-compatible LLM endpoint
  via `INFERKERN_LLM_*` env (swappable: OpenAI, OpenRouter, llama-server); tool
  calling via OpenAI `tools` with text fallback; policy as `allow[]/deny[]` with
  path-aware matching; heuristic planner so repo is demo-able without an API key.
- New package `inferkern/`:
  - `inferkern/agent/goal.py` — goal.yaml loader (env expansion, validation)
  - `inferkern/agent/state.py` — facts + journal.jsonl persistence
  - `inferkern/agent/policy.py` — allow/deny gate (path-aware, deny wins)
  - `inferkern/agent/checks.py` — run `checks/*.sh` (0=pass)
  - `inferkern/agent/probes.py` — discovery (disks, net, mem, cpu, os, mounts, ports)
  - `inferkern/agent/llm.py` — OpenAI-compat chat client (httpx, tool_calls + fallback parser)
  - `inferkern/agent/tools/{exec,file,pkg,service,system}.py` — 12 tools with JSON schemas
  - `inferkern/agent/loop.py` — convergence loop (facts → LLM → gate → exec → journal → checks, budgets)
  - `inferkern/supervisor/sup.py` — mounts, DHCP, state-disk, reap, restart budget, rescue shell; auto-detects Docker vs VM
- Goals: `goals/web-server` (nginx + http-200, budgets, allowlist), `goals/container-host`, `goals/demo-static` (minimal harness target).
- Docker layer (`docker/Dockerfile`, `docker/entrypoint.sh`, `docker/docker-compose.yml`): Alpine 3.20, nginx, Python, supervisor oneshot — `make docker-build && make docker-run` → http://localhost:8080/
- VM layer (`vm/build-rootfs.sh`, `vm/run-qemu.sh`): Alpine rootfs via Docker export, kernel fetch, qcow2 disks, QEMU boot with `init=/usr/local/bin/inferkern-init` — `make vm-build && make vm-run`.
- Harness (`harness/run.py`): rerun-from-clean × N, record success + checks + elapsed; local or --docker; JSON output.
- Infra: `pyproject.toml`, `Makefile`, `.gitignore`, tests (`tests/test_policy_goal.py`, `tests/test_tools.py` — 12 passed), updated `README.md`.
- Verified: imports, goal loading, policy, tool registry, dry-run loop (5 and 20 steps), harness local mode, CLI --help for agent/supervisor/checks.
- Next: test Docker build + real convergence on a Docker host; then QEMU boot + convergence; then wire a real LLM (e.g. OpenAI) and measure convergence rate + cost.

## 2026-10-31 — Post-scaffold: Docker/VM demo verified on host (to do)
- Still to run on a Docker/QEMU-capable machine: `make docker-build && make docker-run` should converge to HTTP 200 in ~10 steps (heuristic) or fewer (LLM); `make vm-build && make vm-run` should boot QEMU and converge similarly. These are ready to run but this host lacks Docker and QEMU (Ubuntu 26.04, 3.3 GiB) — they are exercise-only artifacts until a capable host is available.
## 2026-10-31 — End-to-end proven on host (no Docker/QEMU)
- Fixed loop heuristic: `smoke-test` goal now has a dedicated Python-only path (no apt/nginx), web-server heuristic falls back to `python3 -m http.server` if nginx not available.
- Verified real convergence: `goals/smoke-test` converges in 4 steps locally (writes `/tmp/inferkern-smoke/index.html`, starts `python3 -m http.server 8765`, passes both `http-200.sh` + `file-exists.sh` checks).
- Verified idempotency: second run short-circuits with “All checks already pass”.
- Verified supervisor oneshot path: `python -m inferkern.supervisor.sup --oneshot` for `smoke-test` converges and exits 0 (simulates Docker entrypoint).
- Verified harness: `python -m harness.run --goal smoke-test --runs 2` → 2/2 passed.
- New tests: `tests/test_e2e_smoke.py` (2 tests — agent + supervisor) — total 14 passed, 1 warning.
- Updated README quickstart to list smoke-test as the zero-deps proof.
- Next: Docker build + VM boot on a capable host; then wire a real LLM and measure convergence rate.
- Blocked on this host: `docker.io` + `qemu-system-x86` are available via apt but need passwordless sudo (not granted); demos are ready to run where Docker/QEMU exist.
