# Review: PR #2 — Docker + VM implementation (Proposal A + B)

- **PR:** #2, `kittlab86:feat/docker-and-vm` → `main`
- **Size:** 35 files, +2216 / −0
- **Reviewer:** Muse Code (automated code review, 2026-10-31)
- **Verdict: Close as superseded by PR #1, after salvaging the ideas below** —
  competent work, but it is entirely overlapped by the larger, verified PR #1.

## What the PR does

A compact Proposal A+B implementation: agent package (`agent/` — goal parser,
policy gate, JSONL journal, tool registry, OpenAI-compatible LLM client with
stub mode, converge loop with deterministic nginx fallback), supervisor PID 1
(`supervisor/sup.py`), one `web-server` goal in `goal.md` format, root-level
Docker packaging (`Dockerfile`, `entrypoint.sh`, `compose.yaml`), VM scripts
(`vm/build-rootfs.sh`, `vm/create-disk.sh`, `scripts/run-qemu.sh`), shell
harness (`scripts/harness.sh`), and `unittest`-style tests.

## Strengths

- **Well-structured supervisor.** The `Config` class (env + kernel-cmdline
  overrides), `logging` with `/dev/kmsg` output, label-based volume mounts
  (`INFERKERN_GOAL` / `INFERKERN_STATE`), and graceful shutdown
  (SIGTERM → terminate → kill → reap) are all nicer than PR #1's supervisor
  in these respects. Genuinely worth porting.
- **Simple, correct policy matcher.** `agent/policy.py` does exact-tool plus
  path-prefix matching with deny-wins and no substring tricks — easier to
  audit than PR #1's `_matches()`.
- **`tini` in the Docker image** for reaping and signal forwarding is good
  practice that PR #1's image lacks.
- **Supervisor unit tests need no root/QEMU** (mock-based), which is the
  right testing strategy for PID 1 logic. The goal/parser/journal/tools unit
  tests are likewise cheap and hermetic.
- **Small and readable.** At ~2.2k lines with one goal, it is easy to hold in
  your head — a reasonable v0 shape.

## Issues

### 1. Hand-rolled `goal.md` parser (biggest structural weakness)

`agent/goal.py` parses a bespoke markdown-ish format with ~150 lines of custom
string splitting instead of YAML. Beyond maintainability, it has a real bug:
a multi-line `budget:` block — exactly the form used by the PR's own
`goals/web-server/goal.md` — is silently ignored. `parse_goal_text` only
parses a budget given inline on the `budget:` line (`budget: { max_steps: … }`);
the actual file's indented `max_steps:`/`max_tokens:`/`timeout_min:` lines
fall through every branch and are dropped, so defaults are used unconditionally.
It goes unnoticed only because the defaults happen to equal the file's values.
PR #1's `goal.yaml` + `yaml.safe_load` approach resolves this properly.

### 2. Fragile LLM action parsing

Without native function calling, `_parse_llm_actions` extracts actions with
the greedy regex `\{.*\}` (first `{` to last `}`) and `json.loads`. Any prose
containing braces, multiple JSON objects, or truncated output breaks or
mis-parses. PR #1's OpenAI `tools` + constrained fallback is strictly more
robust.

### 3. Service-status check reintroduces a known false-positive class

`tool_service(status)` passes when the service name appears anywhere in
`ps aux` output — the same substring bug PR #1 explicitly found and fixed
with `pgrep -x nginx` after live testing. Code review alone cannot substitute
for the live verification PR #1 documents.

### 4. Entrypoint oneshot mode is timing-sensitive

`INFERKERN_ONESHOT=1` serves HTTP for a fixed 30s window and then exits 0 so
the harness can probe it. PR #1's `KEEP_ALIVE=0` (exit immediately with the
real converge exit code) gives the harness a deterministic signal instead of
a race window.

### 5. Test-count claims are inconsistent

The PR body says "28 tests passing" in one paragraph and "`pytest 20 passed`
(agent)" in another. Neither number is verifiable from the description, and
the suite mixes `unittest` classes with pytest collection. Minor, but the
verification story should state one reproducible command and its output.

### 6. Miscellaneous

- Repo-root layout (`agent/`, `supervisor/`, `Dockerfile`, `entrypoint.sh`,
  `compose.yaml`) sprawls; PR #1's packaged layout (`inferkern/`, `docker/`,
  `harness/`) scales better and matches the `pyproject.toml` packaging story.
- `vm/build-rootfs.sh` needs root/fakeroot and host `apk` tooling, a heavier
  lift on a Debian/Ubuntu dev machine than PR #1's Docker-export approach.
- No doc updates: after this merge, `README.md` would still say "No bootable
  image yet." PR #1 updates README/PROGRESS/use-cases with the code.
- `bring_up_network()` only attempts DHCP on the first non-loopback
  interface; PR #1 iterates all interfaces. Trivial either way.

## What to salvage into PR #1 (suggested follow-ups)

1. Supervisor `Config` + `logging`/kmsg + kernel-cmdline overrides.
2. Graceful agent shutdown (terminate, wait, kill, reap) on SIGTERM.
3. Label-based goal/state volume mounts (`/dev/disk/by-label/…`).
4. `tini` as Docker init.
5. The mock-based supervisor unit-test approach (no root needed).

## Relation to PR #1

The two PRs implement the same scope and conflict on 4 paths (`.gitignore`,
`goals/web-server/checks/http-200.sh`, `tests/test_tools.py`,
`vm/build-rootfs.sh`), with near-total conceptual overlap
(`agent/` ≡ `inferkern/agent/`, `supervisor/` ≡ `inferkern/supervisor/`, …).
Merging both would fork the codebase. **Recommendation: merge PR #1
(after its requested changes), close this PR as superseded**, optionally
lifting items 1–5 above into follow-up issues.

## Verification performed by reviewer

- Read: `agent/{loop,goal,policy,llm,tools,journal}.py`,
  `supervisor/sup.py`, `Dockerfile`, `entrypoint.sh`, `compose.yaml`,
  `goals/web-server/goal.md`, web-server checks, `vm/build-rootfs.sh`
  (head), `scripts/run-qemu.sh` (head), `tests/test_supervisor.py` (head).
- Traced `parse_goal_text` against the shipped `goal.md` to confirm the
  multi-line `budget:` block is dropped.
- Did not execute Docker/QEMU builds in this review; code-level review only.
