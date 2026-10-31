# inferkern

**The Linux distro where PID 1 is an LLM agent loop.**

inferkern boots a minimal Linux kernel and hands control directly to an
autonomous agent — no systemd, no shell-by-default, no preinstalled services.
The agent discovers hardware, storage, and network, then builds the running
system toward a declared goal: a web server, a container host, a personal
assistant node, or anything else you ask it to become.

> Kernel boots. Agent wakes. System assembles itself.

## The idea in 30 seconds

1. Machine boots (bare metal, VM, or container).
2. The kernel starts the agent loop as init (PID 1).
3. The agent probes its environment: disks, NICs, memory, existing installs.
4. Guided by a goal file (`goals/<name>/goal.yaml`), it partitions, formats,
   installs packages, configures network, and launches services and containers.
5. The result is a working system — converged, not installed.

## Status: Phase 1 scaffold — Docker + VM demo ready

Research (prior art, base options, LLM runtime, init design) is done.
Implementation (Phase 1 + Phase 2 scaffolding) is landed. Builds are not yet
CI-tested but the repo is structured to run end-to-end on a machine with
Docker and/or QEMU.

| Doc | What it covers |
| --- | --- |
| [Vision](docs/vision.md) | Concept, architecture sketch, design principles |
| [Prior art](docs/research/prior-art.md) | Existing LLM-OS and agent-OS projects, and how we differ |
| [Base options](docs/research/base-options.md) | LFS vs Alpine vs Debian/Ubuntu minimal vs Buildroot/Yocto |
| [LLM runtime](docs/research/llm-runtime.md) | Local vs remote inference, boot-time chicken-and-egg |
| [Init design](docs/research/init-design.md) | How an agent loop works as PID 1 |
| [Proposals](docs/proposals.md) | Four build paths, compared |
| [Use cases](docs/use-cases.md) | Candidate primary goals for the agent |
| [Review](docs/review-2026-10-31.md) | Gaps found in theory/proposals and decisions taken |
| [Roadmap](docs/roadmap.md) | Phases and milestones |
| [Progress](PROGRESS.md) | Running log of what has been done |

## Quick start

Prereqs: Python 3.11+, and for demos: Docker (Proposal A) or QEMU (Proposal B).

```bash
pip install -e .             # or: pip install pyyaml httpx rich

# Smoke test (no Docker, no LLM, no root) — proves the whole stack converges:
python -m inferkern.agent.loop goals/smoke-test/goal.yaml --no-llm       # ~4 steps, HTTP 200 on :8765
python -m harness.run --goal smoke-test --runs 2                          # harness: 2/2
python -m pytest -q                                                       # 14 tests

# Dry-run any goal without side effects:
python -m inferkern.agent.loop goals/web-server/goal.yaml --dry-run --no-llm --max-steps 5

# With an LLM (any OpenAI-compatible endpoint):
export INFERKERN_LLM_ENDPOINT=https://api.openai.com/v1
export INFERKERN_LLM_API_KEY=sk-...
export INFERKERN_LLM_MODEL=gpt-4o-mini
python -m inferkern.agent.loop goals/web-server/goal.yaml

# Docker demo (Proposal A) — blank Alpine → nginx on :80:
make docker-build
make docker-run              # serves on http://localhost:8080/  (uses heuristic if no LLM env)
# or with LLM:
INFERKERN_LLM_ENDPOINT=... INFERKERN_LLM_API_KEY=... make docker-run

# VM demo (Proposal B) — needs qemu-system-x86_64 + Docker to build rootfs:
make vm-build
make vm-run                  # boots QEMU, converges, serves on :8080
```

### Goals

Each goal lives in `goals/<name>/`:

```
goals/web-server/
  goal.yaml            # name, llm, budget, accept, constraints
  checks/
    http-200.sh        # 0 = pass, non-zero = fail
    nginx-running.sh
```

Checks are plain shell scripts. The same scripts run inside the agent (during
convergence) and in the harness/CI.

### LLM config

1. Env vars win: `INFERKERN_LLM_ENDPOINT`, `INFERKERN_LLM_API_KEY`, `INFERKERN_LLM_MODEL`.
2. Then `goal.yaml` `llm:` block (supports `$VAR` expansion).
3. If neither is set, the agent runs in heuristic mode — a scripted planner
   that can converge the `web-server` goal without a model. Useful for CI and
   for testing the tool/policy/journal plumbing.

Any OpenAI-compatible endpoint works (OpenAI, OpenRouter, local `llama-server`,
etc.).

## Architecture

```
kernel → inferkern-sup (PID 1, deterministic)
         └─ inferkern-agent (LLM-driven loop, restartable)
             └─ services/containers the agent starts
```

- **Supervisor** (`inferkern/supervisor/sup.py`): mounts, DHCP, reap, restart budget, rescue shell.
- **Agent loop** (`inferkern/agent/loop.py`): goal → facts → LLM → policy gate → tools → journal → checks.
- **Tools** (`inferkern/agent/tools/`): exec, read/write files, apk/apt, service, probe, checks.
- **State** (`inferkern/agent/state.py`): `journal.jsonl` + `facts.json` under `/var/lib/inferkern` (or `./state` in Docker).

See [vision](docs/vision.md) and [init design](docs/research/init-design.md) for the full story.

## Quick verdicts (details in docs)

- **No exact prior art found.** Closest: AI-OS.NET, OpenDAN, AIOS, Osiris, etc. See [prior art](docs/research/prior-art.md).
- **Alpine minimal first**, Debian as glibc fallback, Buildroot later. See [base options](docs/research/base-options.md) and [proposals](docs/proposals.md).
- **First goal: web server → container host** → assistant node. See [use cases](docs/use-cases.md).

## License

MIT. See [LICENSE](LICENSE).
