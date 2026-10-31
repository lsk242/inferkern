"""Tool registry + implementations for Proposal A.

Tools v1: exec, read/write files, apk, probe (lsblk/ip/ss/free), service, check, journal.
All tools are idempotent where applicable and return dict results.
"""
from __future__ import annotations

import os
import pathlib
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass

from .policy import is_allowed
from .journal import Journal


@dataclass
class ToolResult:
    ok: bool
    tool: str
    output: str = ""
    exit_code: int = 0
    extra: dict | None = None


class ToolRegistry:
    def __init__(self, goal, journal: Journal | None = None, dry_run: bool = False):
        self.goal = goal
        self.journal = journal
        self.dry_run = dry_run
        self._handlers = {
            "exec": self.tool_exec,
            "read": self.tool_read,
            "write": self.tool_write,
            "apk": self.tool_apk,
            "probe": self.tool_probe,
            "service": self.tool_service,
            "check": self.tool_check,
            "journal": self.tool_journal,
        }

    def allowed(self, tool: str, target: str | None = None):
        return is_allowed(tool, self.goal.allow, self.goal.deny, target)

    def dispatch(self, tool: str, **kwargs) -> ToolResult:
        # policy gate
        target = kwargs.get("path") or kwargs.get("target") or kwargs.get("package") or kwargs.get("name")
        ok, reason = self.allowed(tool, target)
        if not ok:
            res = ToolResult(ok=False, tool=tool, output=f"policy denied: {reason}", exit_code=1)
            self._journal_entry(tool, kwargs, res, denied=True, reason=reason)
            return res
        handler = self._handlers.get(tool)
        if not handler:
            return ToolResult(ok=False, tool=tool, output=f"unknown tool: {tool}", exit_code=1)
        # dry-run for mutating tools
        if self.dry_run and tool in ("exec", "write", "apk", "service"):
            res = ToolResult(ok=True, tool=tool, output=f"[dry-run] would run {tool} {kwargs}", exit_code=0)
            self._journal_entry(tool, kwargs, res)
            return res
        res = handler(**kwargs)
        self._journal_entry(tool, kwargs, res)
        return res

    def _journal_entry(self, tool, kwargs, res: ToolResult, denied=False, reason=""):
        if self.journal is None:
            return
        entry = {
            "tool": tool,
            "args": {k: (v[:500] if isinstance(v, str) and len(v) > 500 else v) for k, v in kwargs.items()},
            "ok": res.ok,
            "exit_code": res.exit_code,
            "output": res.output[:2000] if res.output else "",
            "denied": denied,
        }
        if reason:
            entry["reason"] = reason
        self.journal.append(entry)

    # -- implementations --

    def tool_exec(self, cmd: str = "", **kw) -> ToolResult:
        if not cmd:
            cmd = kw.get("command", "")
        if not cmd:
            return ToolResult(ok=False, tool="exec", output="no cmd", exit_code=1)
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            out = (r.stdout or "") + (r.stderr or "")
            return ToolResult(ok=r.returncode == 0, tool="exec", output=out[:4000], exit_code=r.returncode)
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, tool="exec", output="timeout 60s", exit_code=124)
        except Exception as e:
            return ToolResult(ok=False, tool="exec", output=str(e), exit_code=1)

    def tool_read(self, path: str = "", **kw) -> ToolResult:
        path = path or kw.get("file", "")
        if not path:
            return ToolResult(ok=False, tool="read", output="no path", exit_code=1)
        try:
            p = pathlib.Path(path)
            if not p.exists():
                return ToolResult(ok=False, tool="read", output=f"not found: {path}", exit_code=1)
            if p.is_dir():
                items = os.listdir(path)
                return ToolResult(ok=True, tool="read", output="\n".join(items))
            txt = p.read_text(errors="replace")
            if len(txt) > 8000:
                txt = txt[:8000] + "\n...truncated"
            return ToolResult(ok=True, tool="read", output=txt)
        except Exception as e:
            return ToolResult(ok=False, tool="read", output=str(e), exit_code=1)

    def tool_write(self, path: str = "", content: str = "", **kw) -> ToolResult:
        path = path or kw.get("file", "")
        content = content if content else kw.get("content", kw.get("text", ""))
        if not path:
            return ToolResult(ok=False, tool="write", output="no path", exit_code=1)
        try:
            p = pathlib.Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            # idempotent: skip if same
            if p.exists():
                try:
                    if p.read_text(errors="replace") == content:
                        return ToolResult(ok=True, tool="write", output=f"unchanged {path}", exit_code=0)
                except Exception:
                    pass
            p.write_text(content)
            return ToolResult(ok=True, tool="write", output=f"wrote {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(ok=False, tool="write", output=str(e), exit_code=1)

    def tool_apk(self, package: str = "", action: str = "add", **kw) -> ToolResult:
        pkg = package or kw.get("packages", kw.get("pkg", ""))
        if not pkg:
            return ToolResult(ok=False, tool="apk", output="no package", exit_code=1)
        # idempotent: check if already installed
        try:
            r = subprocess.run(["apk", "info", "-e", pkg.split()[0]], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return ToolResult(ok=True, tool="apk", output=f"already installed: {pkg}")
        except FileNotFoundError:
            return ToolResult(ok=False, tool="apk", output="apk not found (not Alpine?)", exit_code=1)
        # install
        cmd = ["apk", "add", "--no-cache"] + shlex.split(pkg)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            out = (r.stdout or "") + (r.stderr or "")
            return ToolResult(ok=r.returncode == 0, tool="apk", output=out[:4000], exit_code=r.returncode)
        except Exception as e:
            return ToolResult(ok=False, tool="apk", output=str(e), exit_code=1)

    def tool_probe(self, kind: str = "all", **kw) -> ToolResult:
        kind = kind or kw.get("probe", "all")
        probes = {
            "lsblk": ["lsblk", "-f"],
            "ip": ["ip", "addr"],
            "ss": ["ss", "-tlnp"],
            "free": ["free", "-h"],
            "df": ["df", "-h"],
            "ps": ["ps", "aux"],
        }
        if kind == "all":
            out_parts = []
            for name, cmd in probes.items():
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    out_parts.append(f"=== {name} ===\n" + (r.stdout or r.stderr or "(no output)"))
                except FileNotFoundError:
                    out_parts.append(f"=== {name} ===\n(not found)")
                except Exception as e:
                    out_parts.append(f"=== {name} ===\nerror: {e}")
            return ToolResult(ok=True, tool="probe", output="\n".join(out_parts))
        else:
            cmd = probes.get(kind)
            if not cmd:
                # try raw shell for unknown kind
                return self.tool_exec(cmd=kind)
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return ToolResult(ok=True, tool="probe", output=r.stdout or r.stderr or "")
            except FileNotFoundError:
                return ToolResult(ok=False, tool="probe", output=f"probe {kind} not found", exit_code=1)

    def tool_service(self, name: str = "", action: str = "status", **kw) -> ToolResult:
        name = name or kw.get("service", kw.get("target", ""))
        action = action or kw.get("action", "status")
        if not name:
            return ToolResult(ok=False, tool="service", output="no service name", exit_code=1)
        # Try: service script, openrc, or direct process check
        # For Alpine web-server: nginx
        if action in ("start", "restart", "reload"):
            # try openrc, then direct
            for cmd in [
                ["rc-service", name, action],
                ["service", name, action],
                ["nginx", "-s", "reload"] if name == "nginx" and action == "reload" else None,
            ]:
                if cmd is None:
                    continue
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    if r.returncode == 0:
                        return ToolResult(ok=True, tool="service", output=(r.stdout or r.stderr or f"{name} {action} ok"))
                except FileNotFoundError:
                    continue
            # fallback: try nginx directly
            if name == "nginx":
                try:
                    r = subprocess.run(["nginx"], capture_output=True, text=True, timeout=10)
                    out = (r.stdout or "") + (r.stderr or "")
                    if r.returncode == 0 or "already" in out.lower():
                        return ToolResult(ok=True, tool="service", output=out or "nginx started")
                except FileNotFoundError:
                    return ToolResult(ok=False, tool="service", output="nginx binary not found", exit_code=1)
            return ToolResult(ok=False, tool="service", output=f"failed to {action} {name}", exit_code=1)
        elif action == "stop":
            for cmd in [["rc-service", name, "stop"], ["pkill", name]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if r.returncode == 0:
                        return ToolResult(ok=True, tool="service", output=f"{name} stopped")
                except FileNotFoundError:
                    continue
            return ToolResult(ok=False, tool="service", output=f"failed to stop {name}", exit_code=1)
        else:  # status
            try:
                r = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
                if name in (r.stdout or ""):
                    return ToolResult(ok=True, tool="service", output=f"{name} running")
                return ToolResult(ok=False, tool="service", output=f"{name} not running", exit_code=1)
            except Exception as e:
                return ToolResult(ok=False, tool="service", output=str(e), exit_code=1)

    def tool_check(self, **kw) -> ToolResult:
        """Run acceptance checks from goal.accept list."""
        checks = self.goal.accept or []
        goal_dir = self.goal.goal_dir
        results = []
        all_ok = True
        # candidate roots for check resolution
        _roots = []
        if goal_dir:
            _roots.append(pathlib.Path(goal_dir))
        _roots.extend([pathlib.Path("/etc/inferkern/goals/web-server"), pathlib.Path("goals/web-server"), pathlib.Path("/etc/inferkern"), pathlib.Path(".")])
        for chk in checks:
            p = None
            if goal_dir:
                cand = pathlib.Path(goal_dir) / chk
                if cand.exists():
                    p = cand
            if p is None or not p.exists():
                for r in _roots:
                    cand = r / chk
                    if cand.exists():
                        p = cand
                        break
                if p is None:
                    cand = pathlib.Path(chk)
                    if cand.exists():
                        p = cand
            if p is None or not p.exists():
                results.append(f"FAIL {chk}: not found (goal_dir={goal_dir})")
                all_ok = False
                continue
            try:
                r = subprocess.run(["sh", str(p)], capture_output=True, text=True, timeout=15)
                out = (r.stdout or "") + (r.stderr or "")
                if r.returncode == 0:
                    results.append(f"PASS {chk}: {out.strip()}")
                else:
                    results.append(f"FAIL {chk} (exit {r.returncode}): {out.strip()}")
                    all_ok = False
            except Exception as e:
                results.append(f"FAIL {chk}: {e}")
                all_ok = False
        return ToolResult(ok=all_ok, tool="check", output="\n".join(results), exit_code=0 if all_ok else 1)

    def tool_journal(self, n: int = 20, **kw) -> ToolResult:
        if self.journal is None:
            return ToolResult(ok=True, tool="journal", output="(no journal)")
        tail = self.journal.tail(n=int(n))
        import json
        lines = [json.dumps(e) for e in tail]
        return ToolResult(ok=True, tool="journal", output="\n".join(lines))
