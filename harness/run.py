"""Convergence harness — rerun-from-clean × N, record success rate + cost."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RunResult:
    run: int
    converged: bool
    exit_code: int
    duration_s: float
    output: str


def run_once(image: str, goal: str, port: int = 0, extra_args: list[str] | None = None, timeout: int = 300) -> RunResult:
    cmd = ["docker", "run", "--rm"]
    if port:
        cmd += ["-p", f"{port}:80"]
    cmd += [image, "--goal", goal]
    if extra_args:
        cmd += extra_args
    print(f"  $ {' '.join(cmd)}")
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.monotonic() - start
        output = (result.stdout or "") + (result.stderr or "")
        return RunResult(run=0, converged=result.returncode == 0, exit_code=result.returncode, duration_s=round(elapsed, 1), output=output[-2000:])
    except subprocess.TimeoutExpired as e:
        elapsed = time.monotonic() - start
        output = ""
        if e.stdout:
            output += e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
        if e.stderr:
            output += e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
        return RunResult(run=0, converged=False, exit_code=124, duration_s=round(elapsed, 1), output=f"TIMEOUT after {timeout}s\n" + output[-2000:])


def main():
    parser = argparse.ArgumentParser(description="inferkern convergence harness")
    parser.add_argument("--image", default="inferkern:dev", help="Docker image")
    parser.add_argument("--goal", default="/app/examples/goals/web-server/goal.yaml", help="Goal path inside image")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs")
    parser.add_argument("--timeout", type=int, default=300, help="Per-run timeout (s)")
    parser.add_argument("--json", dest="json_path", default=None, help="Write JSON results to file")
    parser.add_argument("--build", action="store_true", help="Build image before running")
    args = parser.parse_args()

    if args.build:
        print("[harness] building image...")
        r = subprocess.run(["docker", "build", "-f", "docker/Dockerfile", "-t", args.image, "."], cwd=Path(__file__).parent.parent)
        if r.returncode != 0:
            print("Build failed", file=sys.stderr)
            sys.exit(1)

    print(f"[harness] {args.runs} runs — image={args.image} goal={args.goal}")
    results: list[RunResult] = []
    for i in range(args.runs):
        print(f"\n--- run {i+1}/{args.runs} ---")
        result = run_once(args.image, args.goal, timeout=args.timeout)
        result.run = i + 1
        status = "PASS" if result.converged else "FAIL"
        print(f"  [{status}] exit={result.exit_code} duration={result.duration_s}s")
        if not result.converged:
            print(f"  tail:\n{result.output[-800:]}")
        results.append(result)

    passed = sum(1 for r in results if r.converged)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(results)} passed ({100*passed//len(results) if results else 0}%)")
    for r in results:
        print(f"  run {r.run}: {'PASS' if r.converged else 'FAIL'} ({r.duration_s}s, exit {r.exit_code})")

    if args.json_path:
        data = {"runs": [asdict(r) for r in results], "summary": {"passed": passed, "total": len(results)}}
        Path(args.json_path).write_text(json.dumps(data, indent=2) + "\n")
        print(f"Results written to {args.json_path}")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
