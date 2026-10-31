"""exec / probe tools."""
from __future__ import annotations

import subprocess
import shlex


def exec_run(command: str, workdir: str = "", timeout: int = 30) -> dict:
    """Run a shell command, return {exit_code, stdout, stderr, output}."""
    import os

    cwd = workdir if workdir else None
    try:
        r = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        combined = (r.stdout or "") + (r.stderr or "")
        return {
            "exit_code": r.returncode,
            "stdout": (r.stdout or "")[:8000],
            "stderr": (r.stderr or "")[:8000],
            "output": combined[:8000],
        }
    except subprocess.TimeoutExpired as e:
        return {"exit_code": 124, "stdout": "", "stderr": f"timeout after {timeout}s", "output": str(e)[:2000]}
    except Exception as e:
        return {"exit_code": 1, "stdout": "", "stderr": str(e), "output": str(e)[:2000]}


TOOLS = {
    "exec": (
        {
            "name": "exec",
            "description": "Run a shell command on the host. Returns exit_code, stdout, stderr. Prefer idempotent commands where possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "workdir": {"type": "string", "description": "Working directory"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
                },
                "required": ["command"],
            },
        },
        lambda command, workdir="", timeout=30, **_: exec_run(command, workdir=workdir, timeout=timeout),
    ),
}
