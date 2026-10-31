"""Policy allow/deny gate."""
from __future__ import annotations


def _matches_pattern(entry: str, tool: str, target: str | None) -> bool:
    # entry examples: "exec", "apk", "write:/etc", "write:/etc/nginx"
    # tool is normalized tool name; target is optional path/resource
    if ":" in entry:
        e_tool, e_target = entry.split(":", 1)
        if e_tool != tool:
            return False
        if target is None:
            return False
        # prefix match for path-like targets
        return target == e_target or target.startswith(e_target.rstrip("/") + "/") or target.startswith(e_target)
    else:
        return entry == tool


def is_allowed(tool: str, allow: list[str], deny: list[str], target: str | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Deny takes precedence."""
    # deny wins
    for d in deny:
        if _matches_pattern(d, tool, target):
            return False, f"denied by {d}"
    if not allow:
        # if no allow list, allow all except denied
        return True, "no allowlist"
    for a in allow:
        if _matches_pattern(a, tool, target):
            return True, f"allowed by {a}"
    return False, f"not in allowlist {allow}"
