# Review: all open PRs (2026-11-04) + consolidation decision

Scope: every open PR on `lsk242/inferkern` at review time — #1, #2, #3, #4,
#17–#28 (16 PRs). `main` itself is docs-only (research phase, no code), so
every implementation PR is an alternative Proposal A+B stack, not an
increment on shared code. Per-PR deep reviews for #1/#2 already exist
(`review-pr-1-phase1-docker-vm.md`, `review-pr-2-docker-and-vm.md`); this
file covers the full set and records the merge decision.

## Summary table

| PR | Branch | Size | Verdict |
| --- | --- | --- | --- |
| #1 Phase 1+2 scaffold | `feat/phase1-docker-vm` | 88 files, +4518 | **Base for consolidation** (after fixes below) |
| #2 Docker + VM | `feat/docker-and-vm` | 35 files, +2216 | Close as superseded; salvage Config/logging/tini/tests |
| #3 PR reviews | `docs/pr-reviews` | docs only | Superseded by this review; close after merge |
| #4 Proposals A & B | `feat/proposals-a-b` | 41 files, +2464 | Close as superseded; salvage CI |
| #17–#28 recipes (×12) | `feat/recipe-v2-*` | ~39 files each, +2270 | Close as superseded; goals already consolidated |

## #1 — strongest base (merge with fixes)

Packaged layout (`inferkern/`, `docker/`, `harness/`, `vm/`), real YAML
goals, OpenAI tool-calling + heuristic fallback, 16 goals, live-verified
fixes (SIGCHLD, `pgrep -x`, keep-alive). Requested changes, all applied in
the consolidated tree:

1. `supervisor/__init__.py` byte-identical to `sup.py` → minimal re-export.
2. Dead `reap_children()` + unused `candidates` list → deleted.
3. Policy substring matching (`rule in cand_tool`) → exact tool match +
   explicit aliases + path-prefix/glob; decoy-tool regression test added.
4. Pinned `linux-virt-6.6.63-r0.apk` URL → rootfs kernel first, else
   APKINDEX-resolved current version.
5. Minor: `2>/dev/tty` typo, `ps|grep` service check → `pgrep -x`,
   `-it` in `docker-run` (breaks CI) removed, keep-alive now exits on
   SIGTERM within ~1s (verified: `docker stop` 0.5s, exit 0).

## #2 — competent, fully overlapped

Best supervisor ergonomics (Config + kernel-cmdline overrides, kmsg
logging, graceful terminate→kill, label mounts, `tini`, mock-based PID 1
tests) but weaker core: hand-rolled `goal.md` parser silently drops
multi-line `budget:` blocks, greedy-regex LLM parsing, `ps` substring
service check. Salvaged into consolidation: Config/logging/graceful
shutdown, `tini` in the image, mock supervisor tests. Close as superseded.

## #4 — third parallel stack

Clean `agent/` + `qemu/` split, budget tracker, 28 tests, the only PR with
CI (`.github/workflows/ci.yml`). Overlaps #1/#2 throughout (`agent/` vs
`inferkern/agent/`, `qemu/supervisor.py` vs `inferkern/supervisor/`), so it
cannot merge alongside either. Salvaged: CI workflow (adapted to the
packaged layout + Docker smoke). Close as superseded.

## #17–#28 — recipe PRs duplicate the whole stack

Each branches the PR #2 fork and adds exactly one goal (both legacy
`goal.md` and `goal.yaml`) plus its checks: backup, database, DNS, Docker
manager, file server, firewall, home automation, media, monitoring,
network, reverse proxy, VPN. Verified: e.g. #17's
`goals/backup-server/goal.yaml` is byte-identical to the consolidated
goal. All 12 goals + checks already exist in the consolidated `goals/`
(16 total), so merging any recipe PR would re-fork the codebase. Close
all 12 as superseded; future recipes should be goal-only PRs
(`goals/<name>/` + checks) against the shared agent.

## Consolidation (this branch)

Single packaged implementation: agent loop (LLM + heuristic), supervisor
(PID 1 / Docker entrypoint), 16 goals, Docker (Proposal A), QEMU rootfs +
launcher (Proposal B), harness (Proposal D), CI. Verified 2026-11-04:
`pytest` 18 passed (in-image), local + Docker smoke converge, Docker
`web-server` nginx converge exit 0, detached `:8080` HTTP 200, harness
2/2, VM rootfs 132M + `vmlinuz-virt` 11M built (QEMU boot needs
`qemu-system-x86_64` on the host; scripts fail with install hint when
absent). Goals beyond `web-server`/`smoke-test` ship checks and are
LLM-driven; treat them as experimental until each has a harness run.
