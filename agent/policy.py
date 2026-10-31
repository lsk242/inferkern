"""Policy gate — allowlist / denylist enforcement for agent actions."""

from __future__ import annotations

import fnmatch

from agent.goal import Constraints


def _matches(pattern: str, target: str) -> bool:
    """Match with fnmatch; plain strings match exactly or as prefix with ':'.

    Examples:
        'exec' matches tool 'exec'
        'write:/etc' matches target 'write:/etc/nginx/nginx.conf'
        'deny:*.sh' matches via fnmatch
    """
    if ":" in pattern:
        return fnmatch.fnmatch(target, pattern) or target.startswith(pattern + "/") or target == pattern
    return fnmatch.fnmatch(target, pattern) or target == pattern


class PolicyGate:
    """Evaluates whether a proposed action is allowed.

    Constraints model from goal file:
        allow: [exec, write:/etc, write:/srv, apk, service]
        deny:  [mkfs:/dev/vda1, exec:rm -rf /]

    Deny always wins.  If ``allow`` is empty, everything is allowed except denials.
    If ``allow`` is non-empty, action must match at least one allow entry.
    """

    def __init__(self, constraints: Constraints):
        self.allow = list(constraints.allow)
        self.deny = list(constraints.deny)

    def _action_target(self, tool: str, args: dict) -> str:
        """Build a matchable target string from tool + args."""
        # For file writes we include path
        path = args.get("path") or args.get("file") or args.get("target") or ""
        if path:
            return f"{tool}:{path}"
        # For exec we include command prefix for fine-grained deny
        command = args.get("command") or args.get("cmd") or ""
        if command:
            cmd_word = command.strip().split()
            if cmd_word:
                return f"{tool}:{cmd_word[0]}"
        return tool

    def check(self, tool: str, args: dict) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        target = self._action_target(tool, args)

        # Deny check first
        for pat in self.deny:
            if _matches(pat, target) or _matches(pat, tool):
                return False, f"denied by rule '{pat}' (target: {target})"

        # Allow check
        if not self.allow:
            return True, "allowed (no allowlist — default allow)"

        for pat in self.allow:
            if _matches(pat, target) or _matches(pat, tool):
                return True, f"allowed by rule '{pat}'"

        return False, f"not in allowlist (target: {target}, allow: {self.allow})"

    def check_tool(self, tool: str) -> tuple[bool, str]:
        """Shorthand when no args needed."""
        return self.check(tool, {})
