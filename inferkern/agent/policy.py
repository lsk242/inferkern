"""Policy gate: allowlist / denylist for tool actions.

Rules in goal.yaml constraints, e.g.:
  allow: ["exec", "read_file", "write_file:/etc", "pkg_install", "service_start"]
  deny:  ["write_file:/etc/shadow", "exec:rm -rf"]

Matching semantics (exact, auditable -- no substring matching):
- Tool part must match exactly, after alias normalisation
  (read->read_file, write->write_file, list->list_dir, pkg/apk->pkg_install,
  check->run_checks). The bare family name "service" matches any
  service_* tool. Anything else must be the canonical tool name.
- Optional ":target" part matches the call's target (path for file
  tools, command for exec, package list for pkg tools) by exact match,
  directory-prefix match, or fnmatch glob.
- Deny wins over allow. Empty allow list means allow all (minus denials).
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass

ALIASES: dict[str, str] = {
    "read": "read_file",
    "write": "write_file",
    "list": "list_dir",
    "pkg": "pkg_install",
    "apk": "pkg_install",
    "apt": "pkg_install",
    "check": "run_checks",
    "checks": "run_checks",
}

SERVICE_FAMILY = {"service_start", "service_stop", "service_status"}


def _norm_tool(name: str) -> str:
    return ALIASES.get(name, name)


def _parse_rule(rule: str) -> tuple[str, str | None]:
    rule = rule.strip()
    if ":" in rule:
        tool, target = rule.split(":", 1)
        return _norm_tool(tool.strip()), target.strip()
    return _norm_tool(rule), None


def _target_of(tool_name: str, args: dict | None) -> str | None:
    if not args:
        return None
    for key in ("path", "command", "packages", "name", "kind"):
        v = args.get(key)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, list) and v:
            return " ".join(str(x) for x in v)
    return None


def _rule_matches(rule: str, tool_name: str, args: dict | None) -> bool:
    rule_tool, rule_target = _parse_rule(rule)
    if rule_tool == "service":
        tool_ok = tool_name in SERVICE_FAMILY
    else:
        tool_ok = rule_tool == tool_name
    if not tool_ok:
        return False
    if rule_target is None:
        return True
    target = _target_of(tool_name, args)
    if target is None:
        return False
    if fnmatch.fnmatch(target, rule_target):
        return True
    # directory-prefix: rule "/etc" matches "/etc/nginx/nginx.conf"
    base = rule_target.rstrip("/")
    return target == base or target.startswith(base + "/")


@dataclass
class Policy:
    allow: list[str]
    deny: list[str]

    @classmethod
    def from_goal(cls, goal) -> "Policy":
        return cls(allow=list(goal.allow), deny=list(goal.deny))

    def is_allowed(self, tool_name: str, args: dict | None = None) -> tuple[bool, str]:
        """Check if tool call is allowed. Returns (allowed, reason)."""
        for rule in self.deny:
            if _rule_matches(rule, tool_name, args):
                return False, f"denied by rule '{rule}'"
        if not self.allow:
            return True, "allowed (no allowlist)"
        for rule in self.allow:
            if _rule_matches(rule, tool_name, args):
                return True, f"allowed by rule '{rule}'"
        return False, f"not in allowlist {self.allow}"
