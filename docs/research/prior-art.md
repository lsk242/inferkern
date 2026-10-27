# Prior art

**Bottom line: no project found that does exactly this** (LLM agent loop as
Linux init on a minimal kernel). The space clusters into four groups below.
Closest overall: AI-OS.NET and OpenDAN. Most reusable ideas: AIOS (academic),
SchedCP (safe kernel-agent interface), OpenClaw (goal/assistant UX).

Research date: 2026-10-27. Links verified at time of writing.

## 1. AI-native Linux distributions

### AI-OS.NET — AI-Native Linux Distribution
- <https://ai-os.net>
- Status: active, claims bootable GRUB2 ISO (openSUSE Leap 16 base) that boots
  in QEMU, 36 Rust crates, KDE Plasma variant, self-hosted CI.
- Architecture: 11 layers (L0–L10), "constitution" enforced in code:
  **AI proposes, never executes**; typed actions, policy kernel, append-only
  evidence log, rollbackable app capsules.
- Overlap: a real distro where AI is part of the OS design, boots in a VM.
- Difference: AI is a governed advisor layer on top of a conventional
  openSUSE/systemd system — not an agent loop acting as init, not a minimal
  converge-from-kernel design.

### Osiris — Arch + AI agent desktop
- Demo video: <https://www.youtube.com/watch?v=FxnhWNJETr4>
- Status: experimental, unfinished.
- Arch Linux + Cinnamon with an AI agent (powered by OpenCode) fitted into
  the desktop.
- Overlap: "AI OS" positioning on real Linux.
- Difference: desktop assistant bolted onto a full distro; nothing about
  boot, init, or system convergence.

### openKylin — "AI for OS"
- <https://ostechnix.com/openkylin-ai-native-linux-os/>
- Status: announced direction, Chinese distro consortium.
- Strategy shift from "AI on OS" to "AI for OS": a native Linux AI subsystem
  giving developers unified access to models without managing frameworks.
- Overlap: AI subsystem as OS-level concern.
- Difference: platform/API play for a full desktop distro, not agent-driven
  system assembly.

### Anolis OS 27 — "agent native" distro engineering
- <https://asiadaily.org/news/16410/>
- Status: announced by OpenAnolis.
- Agents built into the *process of engineering the distro* (building the OS
  with agents), not agents running inside the OS at boot.
- Difference: about how the sausage is made, not runtime behavior.

### Debian-AI proposal
- <https://lists.debian.org/debian-project/2025/06/msg00030.html>
- Status: mailing-list proposal, June 2025. Interesting framing: shell, GUI,
  and APIs become "skills" of the AI core; the OS reasons about tasks.
- Difference: proposal only, no implementation; still assumes a full Debian
  base with AI on top.

## 2. LLM-as-kernel / agent-OS frameworks (run on top of an OS)

### AIOS — LLM Agent Operating System (academic)
- Paper: <https://arxiv.org/html/2403.16971v5/> · Code: <https://github.com/agiresearch/AIOS>
- Embeds the LLM "into the OS as the brain of the OS": scheduling, context
  switch, memory/storage/tool management *for agents*. "LLM as OS, agents
  as apps."
- Overlap: the OS-abstraction-for-agents mindset, resource isolation between
  agents, tool service layer.
- Difference: a Python framework running on a normal OS; it manages *agents*,
  not disks, partitions, or boot. Highly reusable conceptually (agent
  scheduling, context management) but not a distro.

### OpenDAN — Personal AI OS
- Code: <https://github.com/fiatrete/OpenDAN-Personal-AI-OS>
  (DeepWiki mirror: <https://deepwiki.com/fiatrete/OpenDAN-Personal-AI-OS/5-compute-system>)
- "LLM Kernel" architecture: agents use a configured LLM core (default GPT-4),
  runs as a personal server (Docker), with an `ai_bash` agent that executes
  shell commands. Jarvis/Telegram integration.
- Overlap: closest in spirit to "LLM manages a machine via shell" — persistent
  agent, tool use, personal-server deployment.
- Difference: an application stack on top of an existing OS install; assumes
  the system already exists. No boot/init story, no hardware or storage
  management.

### SchedCP — "Towards Agentic OS" (academic, kernel schedulers)
- Paper: <https://arxiv.org/html/2509.01245v4>
- An LLM-agent framework for Linux schedulers: ~4k lines Rust + 6k Python,
  exposes kernel scheduler interaction to agents via MCP with a
  **safety-first interface** (treats AI as "potentially non-cautious actors",
  defensive interfaces prevent catastrophic failure).
- Overlap: the safety philosophy we need at the init layer.
- Difference: scoped to scheduler tuning, not system assembly.

### AgentKernel
- Explainer: <https://medium.com/@uthpalaja/agentkernel-explained-why-ai-agents-need-their-own-operating-system-ba93e57b5da0>
- A trust layer *above* the normal OS kernel: agent identity registry,
  content trust, tool-action allowlists. Does not replace Linux.
- Overlap: policy/allowlist model for agent tool use.
- Difference: middleware, not a bootable system.

## 3. Adjacent: agents that operate machines

### OpenClaw (ex Clawdbot / Moltbot)
- Guide: <https://openclawai.io/blog/what-is-openclaw-complete-guide/> ·
  Setup: <https://www.bitdoze.com/clawdbot-setup-guide/>
- Open-source, self-hosted 24/7 AI assistant: runs on a VPS/mini-PC/RPi,
  bridges chat apps (WhatsApp, Telegram, Discord, …) to an agent with file,
  shell, browser, and API access. Works with cloud APIs or local models via
  Ollama.
- Overlap: the strongest product reference for "agent that runs your machine".
  A plausible **first goal** for inferkern is literally "become an OpenClaw
  node" (see [use cases](../use-cases.md)).
- Difference: assumes a working OS + Node/toolchain; installed by a human
  following a guide. inferkern inverts this: the agent *is* the installer
  and the init system.

## 4. Adjacent: minimal bases and custom init (no LLM)

- **Minimal Linux Live** (ivandavidov/minimal): script-built tiny distro with
  a readable custom init; boots from ISO/USB, ~tens of MB. Best reference for
  "smallest thing that boots with our own init". See
  [base options](base-options.md).
- **Linux From Scratch**: the manual path to a from-source system. Reference
  value high, maintenance cost prohibitive for v1.
- **Ginux** (Rocky creator, Rust kernel booting Rocky 10 userspace):
  <https://itsfoss.com/news/ginux/> — shows agent-built kernels are feasible,
  but it's about *building* a kernel with AI, not *running* the system with AI.

## Gap analysis

| Capability | Anyone have it? |
| --- | --- |
| Boot to custom minimal init | Yes (MLL, Buildroot, LFS) — no LLM involved |
| LLM agent operating a live Linux box | Yes (OpenClaw, OpenDAN, shell-agents) — on preinstalled systems |
| Governed AI actions inside a distro | Emerging (AI-OS.NET proposes-never-executes, SchedCP safety-first) |
| **LLM agent loop as init, converging bare kernel → working system** | **No — this is the gap inferkern targets** |

## What to borrow

1. From AI-OS.NET: typed actions + policy gate + append-only evidence journal.
2. From SchedCP: defensive interfaces that assume the agent is non-cautious.
3. From OpenDAN/OpenClaw: tool/agent UX and the personal-server deployment shape.
4. From AIOS (paper): agent scheduling, context/memory management vocabulary.
5. From Minimal Linux Live: the minimal bootable base + custom init recipe.
