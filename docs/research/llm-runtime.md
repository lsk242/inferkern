# LLM runtime: where the brains live at boot

The agent loop needs an LLM to reason. At boot time — possibly with no
network, no GPU, and megabytes of RAM — that is a chicken-and-egg problem.
This doc maps the options.

**Recommendation: support both, in order — (1) remote API if network + key
exist, (2) local GGUF server via llama.cpp (`llama-server`) otherwise.
Default dev path is (1); the "real distro" story needs (2).**

## Option A — Remote API (cloud LLM)

The init supervisor brings up networking (DHCP), reads an API endpoint + key
from the goal volume or kernel cmdline, and the agent loop calls it over HTTPS.

- Pros: zero local inference cost — boots on any machine that can run the
  kernel + a small agent binary; always the smartest available model; no
  GPU/VRAM/RAM pressure; simplest v1.
- Cons: requires network at boot (what if the NIC needs firmware the agent
  was supposed to install?); requires a key (secret distribution problem);
  cost per boot-loop; privacy (machine facts leave the box); offline
  machines can't boot to converged state.
- Bootstrapping wrinkle: network config is itself one of the agent's jobs.
  Mitigation: the deterministic supervisor (not the LLM) owns L1–L3 basics —
  DHCP on any link-up interface — before the agent starts. The agent handles
  the fancy stuff (static IPs, VLANs, Wi-Fi, firewall) later.

## Option B — Local inference (GGUF via llama.cpp)

Ship or fetch a quantized GGUF model (e.g. Qwen3-4B Q4_K_M ≈ 2.5 GB,
Llama 3.1 8B Q4 ≈ 4.9 GB) and serve it with `llama-server` (OpenAI-compatible
API on localhost). Ollama is the friendlier wrapper but heavier and more
opinionated; llama.cpp gives flags for context size, GPU layers, and slots.

- Pros: fully offline after first fetch; private; no per-token cost; the
  honest "distro" story — the machine thinks for itself.
- Cons: RAM/VRAM floor — realistically 8 GB+ for small models, 16 GB+ to be
  comfortable; CPU-only inference is slow (tens of seconds per decision —
  acceptable for system config, useless for interactive chat); model file
  must live somewhere (baked into image = multi-GB ISO, or fetched on first
  boot = needs network anyway); small models are worse at the long,
  careful tool-use chains this project needs.
- Hardware note: llama.cpp runs on CPU (AVX2+), CUDA, ROCm/HIP, Vulkan, or
  Apple Silicon. CPU-only on a small VM works but plan for slow loops.

## Option C — Hybrid / staged (recommended)

1. Supervisor brings up basic network.
2. If API endpoint + key are present → agent uses remote API (fast, smart).
3. Else, if a usable local model exists (or can be fetched) and RAM suffices
   → start `llama-server`, agent uses localhost.
4. Else → rescue state: agent (or supervisor script) reports exactly what's
   missing (no key, no model, not enough RAM) and drops to a shell with a
   setup helper. Never spin helplessly.

This gives a smooth ladder: cloud-first development, local-first product.

## Decision matrix

| Scenario | Choice |
| --- | --- |
| Dev in Docker/QEMU on a laptop | A (remote API) — fastest iteration |
| Demo "boots and converges" on a VM | A, with B as stretch goal |
| Offline / airgapped / private | B (local GGUF), needs 8–16 GB RAM |
| Tiny devices (<4 GB RAM) | A only; B infeasible |
| Interactive assistant use case | A (small local models too slow/dumb for chat); B only with GPU |

## Open questions

- Small-model competence: can a 4B–8B local model reliably run 20+ step
  system-admin tool chains? Probably not today — needs eval harnesses
  (success rate per goal) before we can claim offline convergence.
- Secret handling: API keys on the goal volume / kernel cmdline are visible
  in boot logs and `ps`. Phase 1 can accept this; later needs a vault story
  (TPM-sealed, cloud-init-style metadata, or interactive entry).
- Cost guardrails: a confused loop can burn API budget fast. The supervisor
  must enforce per-boot step and token budgets with hard stops.
