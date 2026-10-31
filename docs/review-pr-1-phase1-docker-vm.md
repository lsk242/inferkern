# Review: PR #1 — Phase 1+2 — Docker live verified, VM rootfs, heuristic + supervisor fixes

- **PR:** #1, `kittlab86:feat/phase1-docker-vm` → `main`
- **Size:** 88 files, +4518 / −66
- **Reviewer:** Muse Code (automated code review, 2026-10-31)
- **Verdict: Approve with requested changes** — this is the stronger of the two
  open PRs and should be the one that merges. The changes below are small and
  should not block landing for long.

## What the PR does

Full Phase 1+2 scaffold: an LLM-driven agent loop (`inferkern/agent/`) with a
no-LLM heuristic fallback, a deterministic supervisor (`inferkern/supervisor/`)
that works as both Docker entrypoint and VM PID 1, 16 goal recipes under
`goals/`, Docker packaging (`docker/`), VM scripts (`vm/`), a rerun harness
(`harness/run.py`), a Makefile, tests, and doc updates (README, PROGRESS,
`docs/use-cases.md`, plus the theory-gap analysis in
`docs/review-2026-10-31.md`).

## Strengths

- **Evidence of live testing.** The PR body lists concrete bugs found by
  actually running the stack (SIGCHLD inheritance breaking `subprocess.wait`,
  `pgrep` false-positive on the agent's own cmdline, keep-alive behavior) and
  the code contains the corresponding fixes. That is the single most
  confidence-inspiring property of this PR.
- **Good architecture.** The supervisor/agent split matches `docs/vision.md`
  and `docs/research/init-design.md`: dumb deterministic PID 1, LLM child,
  policy gate, journal, budgets.
- **`goal.yaml` is the right call.** Pure YAML with a real schema
  (`inferkern/agent/goal.py`) instead of the hand-parsed `goal.md` format —
  this resolves theory gap #1 from the included review doc.
- **LLM integration is thought through.** OpenAI-compatible function calling
  with a free-text fallback parser (`inferkern/agent/llm.py`), env-over-goal
  config resolution, token/step/wall-clock budgets, and graceful degradation
  to the heuristic planner after repeated LLM errors.
- **Policy gate with tests.** Path-aware allow/deny with deny-wins semantics
  plus unit tests (`tests/test_policy_goal.py`).
- **E2E test proves convergence.** `tests/test_e2e_smoke.py` runs the real
  loop against the smoke-test goal and asserts checks pass — not a mock.
- **Docs updated in the same PR.** README, PROGRESS.md, and use-cases all move
  with the code, so `main` stays coherent after merge.
- **Harness exits non-zero on failure**, so it can gate CI later.

## Requested changes

### 1. `inferkern/supervisor/__init__.py` is a byte-identical copy of `sup.py` (must fix)

Both files are 384 lines and `cmp` confirms they are identical. This doubles
maintenance cost and confuses imports (`from inferkern.supervisor.sup import …`
vs `from inferkern.supervisor import …` both work by accident). Replace
`__init__.py` with a minimal re-export or an empty file.

### 2. Remove dead/broken `reap_children()` in `sup.py` (should fix)

`reap_children()` contains a long comment thread explaining why its
`waitpid(-1)` approach steals the agent's exit status — and `run_agent()`
correctly does not call it. Dead code that documents its own incorrectness
will confuse the next reader. Delete the function. Same file: `try_network()`
has an unused `candidates` list left over from an earlier iteration — remove it.

### 3. Tighten policy substring matching (should fix)

`_matches()` in `inferkern/agent/policy.py` uses bare substring checks
(`rule_tool in cand_tool`, `rule in cand_tool`). An allow rule of `"read"`
therefore matches any present or future tool whose name merely contains that
substring. For a security gate, matching should be exact tool name, declared
alias (`write` → `write_file`), or `tool:path-prefix` — never substring.
Add a test with a decoy tool name to lock the behavior in.

### 4. Pinned Alpine kernel URL will rot (should fix)

`vm/run-qemu.sh` fetches a revision-pinned apk
(`linux-virt-6.6.63-r0.apk`). Alpine CDNs keep only the latest revision per
release, so this URL 404s as soon as 3.20's kernel is bumped. Prefer
extracting the kernel from the already-built rootfs (`$ROOTFS/boot/…`, which
the script tries first — good) and, as a fallback, resolve the latest
`linux-virt` via `apk fetch` rather than a hardcoded revision.

## Minor observations (non-blocking)

- `probes.is_qemu()` has `2>/dev/tty` where `2>&1` was presumably intended.
  Harmless (fact-gathering only) but worth a one-character fix.
- Supervisor keep-alive path sleeps forever (`while True: time.sleep(3600)`)
  instead of `exec`ing into nginx. Works, but `docker stop` will wait out the
  full stop grace period since SIGTERM is only logged. Consider sleeping in
  short intervals and exiting on SIGTERM.
- `Makefile`'s `docker-run` uses `-it`, which fails under non-TTY CI. The
  harness correctly avoids `-it`; consider dropping it from the Makefile too.
- The 13 non-web/smoke goals (database, vpn-server, …) ship checks but have no
  heuristic planner path and were not exercised per the PR body. That is fine
  for LLM-driven futures, but consider marking them `experimental` in their
  `goal.yaml` descriptions so a passing file listing does not imply coverage.
- E2E tests bind host port 8765 and `pkill` by pattern. Acceptable locally;
  may flake under parallel CI — consider a follow-up issue, not a blocker.
- No CI workflow is added. A follow-up PR adding GitHub Actions
  (`pytest` + `harness --runs 1`, Docker steps) would protect this investment.

## Relation to PR #2

PR #1 and PR #2 are alternative implementations of the same scope (Proposal
A+B) and overlap conceptually throughout, with 4 directly conflicting paths
(`.gitignore`, `goals/web-server/checks/http-200.sh`, `tests/test_tools.py`,
`vm/build-rootfs.sh`). They cannot both merge as-is. **PR #1 should be the
one that merges**: it is a strict superset in scope, uses a cleaner packaged
layout (`inferkern/`, `docker/`, `harness/` vs PR #2's repo-root sprawl),
parses real YAML goals, supports native function calling, and documents live
verification. Before closing PR #2, consider salvaging its best ideas
(see `review-pr-2-docker-and-vm.md`): supervisor `Config` + `logging` + kmsg,
graceful agent shutdown (terminate → kill), kernel-cmdline overrides,
label-based volume mounts, and `tini` in the Docker image.

## Verification performed by reviewer

- Read: `inferkern/agent/{loop,goal,policy,llm,checks,state,probes}.py`,
  all of `inferkern/agent/tools/*.py`, `inferkern/supervisor/sup.py`,
  `harness/run.py`, `Makefile`, `pyproject.toml`, `docker/*`,
  `vm/build-rootfs.sh`, `vm/run-qemu.sh` (head), all of `tests/`,
  `docs/review-2026-10-31.md`, web-server and smoke-test goals and checks.
- Confirmed via `cmp` that `supervisor/__init__.py` ≡ `sup.py`.
- Counted tests: 8 (policy/goal) + 2 (e2e) + 4 (tools) = 14, matching the PR
  body's claim.
- Did not execute Docker/QEMU builds in this review (no container runtime
  asserted); code-level review only.
