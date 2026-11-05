"""Package manager tools (apk / apt abstraction)."""
from __future__ import annotations

import shutil
import subprocess


def _run(cmd: str, timeout: int = 120) -> dict:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        return {"exit_code": r.returncode, "output": out[:8000], "stdout": (r.stdout or "")[:8000], "stderr": (r.stderr or "")[:4000]}
    except subprocess.TimeoutExpired as e:
        return {"exit_code": 124, "output": f"timeout: {e}"[:2000]}
    except Exception as e:
        return {"exit_code": 1, "output": str(e)[:2000]}


def pkg_install(packages: str | list[str], update: bool = False) -> dict:
    """Install packages via apk or apt-get (auto-detected). Idempotent-ish."""
    if isinstance(packages, str):
        pkgs = packages.strip().split()
    else:
        pkgs = list(packages)
    if not pkgs:
        return {"error": "no packages given", "exit_code": 1, "output": ""}

    if shutil.which("apk"):
        # Alpine
        if update:
            _run("apk update", timeout=60)
        cmd = "apk add --no-cache " + " ".join(pkgs)
        r = _run(cmd, timeout=300)
        r["manager"] = "apk"
        return r
    elif shutil.which("apt-get"):
        # Debian/Ubuntu
        if update or True:  # always update once per run if needed
            # check if we already updated recently via marker
            pass
        # apt-get update is best-effort; don't fail if it was done elsewhere
        if update:
            _run("apt-get update -qq", timeout=120)
        cmd = "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends " + " ".join(pkgs)
        r = _run(cmd, timeout=300)
        r["manager"] = "apt-get"
        return r
    else:
        return {"error": "no supported package manager (apk, apt-get) found", "exit_code": 1, "output": ""}


def pkg_update() -> dict:
    if shutil.which("apk"):
        return _run("apk update", timeout=60)
    elif shutil.which("apt-get"):
        return _run("apt-get update -qq", timeout=120)
    return {"error": "no package manager", "exit_code": 1, "output": ""}


TOOLS = {
    "pkg_install": (
        {
            "name": "pkg_install",
            "description": "Install packages via the system package manager (apk on Alpine, apt on Debian). Idempotent — safe to re-run. Accepts space-separated string or array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {"type": "string", "description": "Space-separated package names, e.g. 'nginx curl'"},
                    "update": {"type": "boolean", "description": "Refresh package index first (default false)", "default": False},
                },
                "required": ["packages"],
            },
        },
        lambda packages, update=False, **_: pkg_install(packages, update=update),
    ),
    "pkg_update": (
        {
            "name": "pkg_update",
            "description": "Refresh package index (apk update / apt-get update).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        lambda **_: pkg_update(),
    ),
}
