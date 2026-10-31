"""Acceptance check runner."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class CheckResult:
    check: str  # path to check script
    passed: bool
    output: str
    exit_code: int


def run_check(script: str | Path, timeout: int = 30) -> CheckResult:
    """Run a single check script. Exit 0 = pass."""
    script = str(script)
    log.info("check: %s", script)
    try:
        result = subprocess.run(["bash", script], capture_output=True, text=True, timeout=timeout)
        output = (result.stdout or "") + (result.stderr or "")
        return CheckResult(check=script, passed=result.returncode == 0, output=output.strip(), exit_code=result.returncode)
    except FileNotFoundError:
        return CheckResult(check=script, passed=False, output=f"check script not found: {script}", exit_code=127)
    except subprocess.TimeoutExpired:
        return CheckResult(check=script, passed=False, output=f"check timed out after {timeout}s: {script}", exit_code=124)
    except Exception as e:
        return CheckResult(check=script, passed=False, output=str(e), exit_code=1)


def run_checks(scripts: list[str | Path], timeout: int = 30) -> list[CheckResult]:
    return [run_check(s, timeout=timeout) for s in scripts]


def all_passed(results: list[CheckResult]) -> bool:
    return all(r.passed for r in results)


def resolve_checks(accept: list[str], goal_dir: str | Path) -> list[str]:
    """Resolve accept entries (relative to goal dir) to absolute paths."""
    base = Path(goal_dir)
    resolved: list[str] = []
    for entry in accept:
        p = Path(entry)
        if p.is_absolute():
            resolved.append(str(p))
        else:
            resolved.append(str(base / p))
    return resolved
