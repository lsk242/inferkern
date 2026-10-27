# Use cases: what should the agent converge *to*?

The agent needs a primary goal to guide it — "manage the system" is too vague
to test. Candidate goals, ordered by recommended sequence. Each goal ships as
`goal.md` + `checks/*.sh` + expected end state for the simulation harness.

## 1. Web server (first goal — recommended)

- Goal: serve a static site / reverse-proxy an app over HTTP(S) on port 80/443.
- Why first: concrete, small tool surface (packages, files, one service,
  firewall), trivially verifiable (`curl` returns 200), maps directly to
  Proposal A/B exit criteria.
- Acceptance checks: HTTP 200 on `/`, service survives agent-loop restart,
  reboot re-converges without human input.

## 2. Container host

- Goal: Docker/Podman running, a declared set of containers up (e.g. nginx +
  postgres), volumes on the right disk, restart policies set.
- Why second: exercises storage management (volumes, mounts), multi-service
  orchestration, and the "run applications" half of the vision.
- Note: Docker on musl/Alpine works but has quirks; this goal may force the
  glibc-fallback decision (see [base options](research/base-options.md)).

## 3. OpenClaw-style assistant node

- Goal: the machine becomes a self-hosted AI assistant box (chat gateway +
  agent + tools), i.e. "install and configure OpenClaw toward a declared
  personality/accounts setup".
- Why third: the most ambitious and most on-brand — the machine assembles
  its own higher-level agent. But it needs 1+2 working first (services,
  containers, secrets) plus secret injection (chat tokens, API keys), which
  is its own design problem (see [llm runtime](research/llm-runtime.md)).
- This is the "it could just be another agent like OpenClaw" endgame:
  inferkern converges bare metal into an OpenClaw node with zero manual setup.

## 4. Later candidates (not sequenced)

- **Home server / NAS**: storage pooling, SMB/NFS shares, backups. Heavy on
  partitioning/filesystem decisions — great agent reasoning demo.
- **Dev box**: users, SSH keys, toolchains, dotfiles from a repo.
- **Kiosk / appliance**: single-purpose locked-down image (signage, sensor
  gateway). Pairs well with the Buildroot phase.
- **Rescue/diagnostics**: boot unknown hardware, report what's there, fix
  what's fixable. Actually a degenerate case of the discovery layer every
  goal needs.

## Goal format (draft, v1)

```markdown
# goal.md
name: web-server
llm: { endpoint: $LLM_ENDPOINT, api_key: $LLM_API_KEY }  # or: local: qwen3-4b.gguf
budget: { max_steps: 60, max_tokens: 200000, timeout_min: 30 }
accept: [checks/http-200.sh, checks/service-persists.sh]
constraints:
  allow: [exec, apk, write:/etc, write:/srv, service]
  deny: [mkfs:/dev/vda1]          # don't touch existing install
```

Checks are plain shell scripts returning 0/1 — runnable by the agent during
convergence and by the harness afterward. Same scripts, both places.
