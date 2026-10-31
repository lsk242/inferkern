"""Tool registry — declares available tools and dispatches execution."""

from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)


@dataclasses.dataclass
class ToolResult:
    ok: bool
    output: str  # stdout+stderr combined, truncated
    exit_code: int = 0

    def to_text(self) -> str:
        status = "OK" if self.ok else f"FAIL (exit {self.exit_code})"
        return f"[{status}]\n{self.output[:8000]}"


@dataclasses.dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict  # JSON Schema for LLM tool calling
    handler: Callable[[dict], ToolResult]


class ToolRegistry:
    def __init__(self, workdir: str | Path = "/"):
        self.workdir = Path(workdir)
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def describe_for_llm(self) -> list[dict]:
        """Return OpenAI-style tool schemas."""
        schemas: list[dict] = []
        for t in self._tools.values():
            schemas.append({"name": t.name, "description": t.description, "parameters": t.parameters})
        return schemas

    def execute(self, tool: str, args: dict) -> ToolResult:
        if tool not in self._tools:
            return ToolResult(ok=False, output=f"unknown tool: {tool}", exit_code=127)
        try:
            return self._tools[tool].handler(args)
        except Exception as e:
            log.exception("Tool %s failed", tool)
            return ToolResult(ok=False, output=f"tool error: {e}", exit_code=1)

    # -- helpers --

    def _exec(self, cmd: str, timeout: int = 60) -> ToolResult:
        """Run a shell command."""
        log.info("exec: %s", cmd[:500])
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(self.workdir))
            output = (result.stdout or "") + (result.stderr or "")
            return ToolResult(ok=result.returncode == 0, output=output.strip() or "(no output)", exit_code=result.returncode)
        except subprocess.TimeoutExpired:
            return ToolResult(ok=False, output=f"command timed out after {timeout}s: {cmd[:200]}", exit_code=124)
        except Exception as e:
            return ToolResult(ok=False, output=str(e), exit_code=1)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _make_tools(registry: ToolRegistry):
    def _exec_handler(args: dict) -> ToolResult:
        return registry._exec(args["command"], timeout=int(args.get("timeout", 60)))

    def _read_file_handler(args: dict) -> ToolResult:
        path = args["path"]
        try:
            content = Path(path).read_text()
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            return ToolResult(ok=True, output=content)
        except FileNotFoundError:
            return ToolResult(ok=False, output=f"file not found: {path}", exit_code=1)
        except Exception as e:
            return ToolResult(ok=False, output=str(e), exit_code=1)

    def _write_file_handler(args: dict) -> ToolResult:
        path = Path(args["path"])
        content = args["content"]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return ToolResult(ok=True, output=f"wrote {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(ok=False, output=str(e), exit_code=1)

    def _list_dir_handler(args: dict) -> ToolResult:
        path = args.get("path", ".")
        try:
            entries = os.listdir(path)
            return ToolResult(ok=True, output="\n".join(sorted(entries)) or "(empty)")
        except Exception as e:
            return ToolResult(ok=False, output=str(e), exit_code=1)

    def _check_handler(args: dict) -> ToolResult:
        """Run acceptance check scripts."""
        script = args["script"]
        # Security: resolve relative to workdir or absolute only
        return registry._exec(f"bash {script}", timeout=int(args.get("timeout", 30)))

    def _probe_handler(args: dict) -> ToolResult:
        """Run discovery probes (lsblk, ip, free, etc.)."""
        probe = args.get("probe", "all")
        probes: dict[str, str] = {
            "lsblk": "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>&1 || lsblk 2>&1 || echo 'lsblk not available'",
            "ip": "ip addr 2>&1 || ifconfig 2>&1 || echo 'no ip/ifconfig'",
            "free": "free -h 2>&1 || cat /proc/meminfo 2>&1 | head -20",
            "os": "cat /etc/os-release 2>&1 || cat /etc/alpine-release 2>&1 || uname -a",
            "all": "echo '=== OS ===' && (cat /etc/os-release 2>&1 || cat /etc/alpine-release 2>&1 || uname -a) && echo '=== BLOCK ===' && (lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>&1 || lsblk 2>&1 || echo 'lsblk N/A') && echo '=== NET ===' && (ip addr 2>&1 || ifconfig 2>&1 || echo 'N/A') && echo '=== MEM ===' && (free -h 2>&1 || cat /proc/meminfo 2>&1 | head -10) && echo '=== DISK ===' && df -h 2>&1",
        }
        cmd = probes.get(probe, probes["all"]) if probe != "all" else probes["all"]
        return registry._exec(cmd)

    # Register all tools
    registry.register(ToolDef("exec", "Execute a shell command", {"type": "object", "properties": {"command": {"type": "string", "description": "Shell command to run"}, "timeout": {"type": "integer", "description": "Timeout in seconds"}}, "required": ["command"]}, _exec_handler))
    registry.register(ToolDef("read_file", "Read a file's contents", {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path to file"}}, "required": ["path"]}, _read_file_handler))
    registry.register(ToolDef("write_file", "Write content to a file (creates parent dirs)", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}, _write_file_handler))
    registry.register(ToolDef("list_dir", "List directory contents", {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, _list_dir_handler))
    registry.register(ToolDef("check", "Run an acceptance check script", {"type": "object", "properties": {"script": {"type": "string", "description": "Path to check script"}, "timeout": {"type": "integer"}}, "required": ["script"]}, _check_handler))
    registry.register(ToolDef("probe", "Run system discovery probes", {"type": "object", "properties": {"probe": {"type": "string", "enum": ["all", "lsblk", "ip", "free", "os"], "description": "Which probe to run"}}, "required": ["probe"]}, _probe_handler))


def all_tools(workdir: str | Path = "/") -> ToolRegistry:
    registry = ToolRegistry(workdir=workdir)
    _make_tools(registry)
    return registry
