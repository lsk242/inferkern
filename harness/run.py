"""Harness (Proposal D v0) — rerun Docker convergence and record success/cost."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_once(goal: str, run_id: int, use_docker: bool, workdir: Path) -> dict:
    """Run one convergence attempt."""
    t0 = time.time()
    result: dict = {"run": run_id, "goal": goal, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    if use_docker:
        # Docker path — use sudo if needed (lsk may be in docker group but not yet effective)
        env = os.environ.copy()
        image = os.environ.get("INFERKERN_IMAGE", "inferkern:dev")
        # Detect docker command (may need sudo)
        import shutil
        docker_bin = "docker"
        # test if docker works without sudo; if not, try sudo
        try:
            _test = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
            if "permission denied" in (_test.stderr or "").lower() or _test.returncode != 0 and "permission" in (_test.stderr or "").lower():
                # try sudo
                _test2 = subprocess.run(["sudo", "docker", "ps"], capture_output=True, text=True, timeout=5)
                if _test2.returncode == 0:
                    docker_bin = "sudo docker"
        except Exception:
            pass
        # Split for subprocess (handle "sudo docker" -> ["sudo","docker"])
        docker_cmd = docker_bin.split()
        # inferkern docker args — KEEP_ALIVE=0 so container exits after converge (harness needs exit code)
        cmd = docker_cmd + [
            "run",
            "--rm",
            "-e",
            f"INFERKERN_LLM_ENDPOINT={env.get('INFERKERN_LLM_ENDPOINT','')}",
            "-e",
            f"INFERKERN_LLM_API_KEY={env.get('INFERKERN_LLM_API_KEY','')}",
            "-e",
            f"INFERKERN_LLM_MODEL={env.get('INFERKERN_LLM_MODEL','')}",
            "-e",
            f"INFERKERN_GOAL=/goals/{goal}/goal.yaml",
            "-e",
            "INFERKERN_KEEP_ALIVE=0",
            "-v",
            f"{workdir}/goals:/goals:ro",
            image,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            result["exit_code"] = r.returncode
            result["stdout_tail"] = (r.stdout or "")[-4000:]
            result["stderr_tail"] = (r.stderr or "")[-4000:]
            result["success"] = r.returncode == 0
        except subprocess.TimeoutExpired:
            result["exit_code"] = 124
            result["success"] = False
            result["error"] = "timeout"
        except FileNotFoundError:
            result["exit_code"] = 127
            result["success"] = False
            result["error"] = "docker not found"
    else:
        # Local heuristic path (no docker)
        goal_path = workdir / f"goals/{goal}/goal.yaml"
        state_dir = workdir / f"state-harness-{run_id}"
        # clean state
        import shutil
        shutil.rmtree(state_dir, ignore_errors=True)
        env = os.environ.copy()
        env["INFERKERN_STATE_DIR"] = str(state_dir)
        env["INFERKERN_GOAL"] = str(goal_path)
        env["INFERKERN_NO_LLM"] = "1"
        # ensure goal deps available: create minimal needed dirs/files for checks
        cmd = [sys.executable, "-m", "inferkern.agent.loop", str(goal_path), "--state-dir", str(state_dir)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env, cwd=str(workdir))
            result["exit_code"] = r.returncode
            result["stdout_tail"] = (r.stdout or "")[-4000:]
            result["stderr_tail"] = (r.stderr or "")[-4000:]
            result["success"] = r.returncode == 0

            # run checks explicitly for reporting
            from inferkern.agent.goal import load_goal
            from inferkern.agent.checks import run_checks, summary

            try:
                g = load_goal(goal_path)
                checks = run_checks(g)
                result["checks"] = [{"name": c.name, "passed": c.passed, "output": c.output[:500]} for c in checks]
                result["checks_summary"] = summary(checks)
                # success means checks truly passed
                result["checks_pass"] = all(c.passed for c in checks) if checks else False
            except Exception as e:
                result["checks_error"] = str(e)
        except subprocess.TimeoutExpired:
            result["exit_code"] = 124
            result["success"] = False
            result["error"] = "timeout"
        except Exception as e:
            result["exit_code"] = 1
            result["success"] = False
            result["error"] = str(e)

    result["elapsed_s"] = round(time.time() - t0, 1)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="inferkern harness — rerun convergence and score it")
    ap.add_argument("--goal", default="web-server", help="Goal name under goals/")
    ap.add_argument("--runs", type=int, default=2, help="Number of runs from clean state")
    ap.add_argument("--docker", action="store_true", help="Use docker (default: local heuristic if docker absent)")
    ap.add_argument("--json", dest="json_out", default="", help="Write JSON results to file")
    args = ap.parse_args()

    # resolve workdir (repo root)
    workdir = Path(__file__).resolve().parent.parent
    # if running as module from repo root, adjust
    if not (workdir / "goals").exists():
        workdir = Path.cwd()

    use_docker = args.docker
    if not use_docker:
        # auto-detect docker
        import shutil
        if shutil.which("docker"):
            print("[harness] docker found — use --docker to run via docker, defaulting to local mode")
        else:
            print("[harness] docker not found — running local heuristic mode")

    print(f"[harness] goal={args.goal} runs={args.runs} mode={'docker' if use_docker else 'local'}")

    results = []
    for i in range(1, args.runs + 1):
        print(f"\n[harness] --- run {i}/{args.runs} ---")
        r = run_once(args.goal, i, use_docker, workdir)
        results.append(r)
        status = "PASS" if r.get("success") else "FAIL"
        print(f"[harness] run {i}: {status} exit={r.get('exit_code')} elapsed={r.get('elapsed_s')}s")
        if r.get("checks_summary"):
            print(r["checks_summary"])
        if not r.get("success") and r.get("stdout_tail"):
            print(r["stdout_tail"][-2000:])

    successes = sum(1 for r in results if r.get("success"))
    print(f"\n[harness] === summary: {successes}/{args.runs} passed ===")
    for r in results:
        flag = "✓" if r.get("success") else "✗"
        print(f"  {flag} run {r['run']}: exit={r.get('exit_code')} elapsed={r.get('elapsed_s')}s")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2))
        print(f"[harness] wrote {args.json_out}")

    # exit non-zero if any failed (so CI can gate on it)
    if successes < args.runs:
        sys.exit(1)


if __name__ == "__main__":
    main()
