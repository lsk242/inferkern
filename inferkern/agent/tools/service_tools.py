"""Service management tools (openrc, systemd, or direct process supervision)."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


def _run(cmd: str, timeout: int = 30) -> dict:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"exit_code": r.returncode, "output": ((r.stdout or "") + (r.stderr or ""))[:4000]}
    except Exception as e:
        return {"exit_code": 1, "output": str(e)[:2000]}


def service_start(name: str) -> dict:
    """Start a service (tries openrc, systemd, then direct via rc-service/service)."""
    # try known supervisors in order
    # openrc
    if shutil.which("rc-service"):
        r = _run(f"rc-service {name} start")
        if r["exit_code"] == 0:
            r["manager"] = "openrc"
            return r
        # try with --ifnotstarted or just return what we got, try fallback
        # some Alpine images need rc-update first
        _run(f"rc-update add {name} default 2>&1")
        r2 = _run(f"rc-service {name} start")
        if r2["exit_code"] == 0:
            r2["manager"] = "openrc"
            return r2
    # systemd
    if shutil.which("systemctl"):
        r = _run(f"systemctl start {name}")
        if r["exit_code"] == 0:
            r["manager"] = "systemd"
            return r
    # sysv / service shim
    if shutil.which("service"):
        r = _run(f"service {name} start")
        if r["exit_code"] == 0:
            r["manager"] = "service"
            return r
    # direct binary fallback: nginx, etc. — try starting binary directly
    # for nginx specifically
    if name == "nginx":
        # nginx -t first
        t = _run("nginx -t 2>&1")
        if t["exit_code"] != 0:
            return {"exit_code": t["exit_code"], "output": f"nginx -t failed: {t['output']}", "manager": "direct"}
        r = _run("nginx 2>&1 || nginx -g 'daemon off;' &")
        time.sleep(0.5)
        # check if nginx is listening
        check = _run("ss -tlnp 2>&1 | grep -q :80 && echo listening || echo not-listening; ps aux 2>&1 | grep -v grep | grep nginx | head -5")
        r["manager"] = "direct"
        r["check"] = check["output"]
        # nginx master stays running if invocation succeeded
        return r
    return {"exit_code": 1, "output": f"no service manager could start '{name}' (tried rc-service, systemctl, service)", "manager": "none"}


def service_stop(name: str) -> dict:
    if shutil.which("rc-service"):
        r = _run(f"rc-service {name} stop")
        if r["exit_code"] == 0:
            return r
    if shutil.which("systemctl"):
        r = _run(f"systemctl stop {name}")
        if r["exit_code"] == 0:
            return r
    if name == "nginx":
        return _run("nginx -s stop 2>&1; nginx -s quit 2>&1; pkill nginx 2>&1; echo stopped")
    return {"exit_code": 1, "output": f"could not stop {name}"}


def service_status(name: str) -> dict:
    if shutil.which("rc-service"):
        r = _run(f"rc-service {name} status")
        # openrc status returns non-zero when stopped but output is still useful
        if r["output"]:
            r["manager"] = "openrc"
            return r
    if shutil.which("systemctl"):
        r = _run(f"systemctl is-active {name}; systemctl status {name} 2>&1 | head -20")
        if r["output"]:
            r["manager"] = "systemd"
            return r
    # fallback: check process / port
    r = _run(f"ps aux 2>&1 | grep -v grep | grep {name} | head -5; echo ---; ss -tlnp 2>&1 | grep {name} | head -5")
    r["manager"] = "proc"
    return r


TOOLS = {
    "service_start": (
        {
            "name": "service_start",
            "description": "Start a system service (nginx, etc.). Tries OpenRC/systemd/direct. Idempotent-ish.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Service name, e.g. nginx"}},
                "required": ["name"],
            },
        },
        lambda name, **_: service_start(name),
    ),
    "service_stop": (
        {
            "name": "service_stop",
            "description": "Stop a system service.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        lambda name, **_: service_stop(name),
    ),
    "service_status": (
        {
            "name": "service_status",
            "description": "Check if a service is running.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        lambda name, **_: service_status(name),
    ),
}
