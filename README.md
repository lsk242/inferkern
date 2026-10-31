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
4. Guided by a goal file (`/etc/inferkern/goal.md`), it partitions, formats,
   installs packages, configures network, and launches services and containers.
5. The result is a working system — converged, not installed.

## Quick start

```bash
pip install -e ".[dev]"          # or: uv pip install -e ".[dev]"
pytest                           # 28 tests

# Proposal A — Docker (no API key needed, uses mock provider)
docker build -f docker/Dockerfile -t inferkern:dev .
docker run --rm -p 8080:80 inferkern:dev
curl http://localhost:8080/      # should return 200 with inferkern page

# With a real LLM (set LLM_ENDPOINT + LLM_API_KEY)
docker run --rm -p 8080:80 \
  -v $(pwd)/examples/goals/web-server/goal.llm.yaml:/etc/inferkern/goal.yaml:ro \
  -e LLM_ENDPOINT -e LLM_API_KEY inferkern:dev

# Proposal B — QEMU (requires qemu-system-x86_64)
make qemu-rootfs                 # build Alpine rootfs (needs docker)
qemu/run.sh --disk /tmp/disk.qcow2

# Harness
make harness                     # 3× Docker convergence runs
```

## Status: proposals A & B implemented

- **Proposal A (Docker):** agent loop converges Alpine → nginx web server in a container
- **Proposal B (QEMU):** `inferkern-sup` supervisor boots Alpine in QEMU as PID 1, supervises agent
- **Next:** Buildroot appliance image (Proposal C), offline/local LLM, bare-metal boot

| Doc | What it covers |
| --- | --- |
| [Vision](docs/vision.md) | Concept, architecture sketch, design principles |
| [Prior art](docs/research/prior-art.md) | Existing LLM-OS and agent-OS projects, and how we differ |
| [Base options](docs/research/base-options.md) | LFS vs Alpine vs Debian/Ubuntu minimal vs Buildroot/Yocto |
| [LLM runtime](docs/research/llm-runtime.md) | Local vs remote inference, boot-time chicken-and-egg |
| [Init design](docs/research/init-design.md) | How an agent loop works as PID 1 |
| [Proposals](docs/proposals.md) | Four build paths, compared |
| [Use cases](docs/use-cases.md) | Candidate primary goals for the agent |
| [Roadmap](docs/roadmap.md) | Phases and milestones |
| [Progress](PROGRESS.md) | Running log of what has been done |

## Quick verdicts (details in docs)

- **No exact prior art found.** Closest projects: AI-OS.NET (governed AI-native
  distro, Rust, boots in QEMU), OpenDAN (LLM-as-kernel personal server),
  AIOS (academic agent-OS framework), Osiris (Arch + agent desktop).
  None run an LLM agent loop as PID 1 on a minimal kernel. See
  [prior art](docs/research/prior-art.md).
- **Don't start from scratch.** Start from Alpine minimal (or Debian netinst
  for glibc), strip down, prove the agent-init loop in Docker and QEMU first.
  Graduate to Buildroot only if we need a true from-source appliance.
  See [base options](docs/research/base-options.md) and
  [proposals](docs/proposals.md).
- **First agent goal: web server / container host.** Concrete, testable,
  and a natural stepping stone to an OpenClaw-style assistant node.
  See [use cases](docs/use-cases.md).

## License

MIT. See [LICENSE](LICENSE).
