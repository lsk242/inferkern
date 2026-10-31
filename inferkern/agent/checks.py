"""Run acceptance checks (shell scripts returning 0 = pass)."""
from __future__ import annotations

import subprocess
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    passed: bool
    output: str
    elapsed_s: float
    path: Path | None = None


def run_checks(
    goal,
    extra_env: dict[str, str] | None = None,
    timeout: int = 30,
) -> list[CheckResult]:
    """Run all checks listed in goal. Returns one result per check."""
    results: list[CheckResult] = []
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    for p in goal.check_paths():
        if not p.exists():
            results.append(
                CheckResult(name=p.name, passed=False, output=f"check not found: {p}", elapsed_s=0, path=p)
            )
            continue
        # ensure executable
        try:
            import time as _time

            t0 = _time.time()
            proc = subprocess.run(
                ["/bin/sh", str(p)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(p.parent),
            )
            elapsed = _time.time() - t0
            output = (proc.stdout or "") + (proc.stderr or "")
            results.append(
                CheckResult(
                    name=p.name,
                    passed=proc.returncode == 0,
                    output=output.strip(),
                    elapsed_s=elapsed,
                    path=p,
                )
            )
        except subprocess.TimeoutExpired:
            results.append(
                CheckResult(name=p.name, passed=False, output="timeout", elapsed_s=timeout, path=p)
            )
        except Exception as e:
            results.append(CheckResult(name=p.name, passed=False, output=str(e), elapsed_s=0, path=p))
    return results


def all_passed(results: list[CheckResult]) -> bool:
    return bool(results) and all(r.passed for r in results)


def summary(results: list[CheckResult]) -> str:
    lines = []
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.name}: {r.output[:300] if r.output else '(no output)'}")
    return "\n".join(lines)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Run inferkern goal checks")
    ap.add_argument("goal", nargs="?", default=os.environ.get("INFERKERN_GOAL", "goals/web-server/goal.yaml"))
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    from .goal import load_goal

    goal = load_goal(args.goal)
    results = run_checks(goal, timeout=args.timeout)
    for r in results:
        print(summary([r]))
    if all_passed(results):
        print("\nAll checks PASSED.")
    else:
        print("\nSome checks FAILED.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
