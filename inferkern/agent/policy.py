"""Policy gate: allowlist / denylist for tool actions.

Rules in goal.yaml constraints:
  allow: ["exec", "read", "write:/etc", "pkg", "service", "probe", "check"]
  deny:  ["mkfs:/dev/vda1", "exec:dd", ...]

Matching is prefix/glob-based. Deny wins over allow. Empty allow = allow all (except deny).
Tool names are the registry names (exec, read_file, write_file, pkg_install, etc.).
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass


@dataclass
class Policy:
    allow: list[str]
    deny: list[str]

    @classmethod
    def from_goal(cls, goal) -> "Policy":
        return cls(allow=list(goal.allow), deny=list(goal.deny))

    def is_allowed(self, tool_name: str, args: dict | None = None) -> tuple[bool, str]:
        """Check if tool call is allowed. Returns (allowed, reason)."""
        # Build candidate strings to match: tool name and tool with arg-derived qualifiers
        candidates = [tool_name]
        if args:
            # e.g. write_file path=/etc/nginx/nginx.conf -> "write_file:/etc/nginx/nginx.conf" and prefixes
            for v in args.values():
                if isinstance(v, str) and v.startswith("/"):
                    candidates.append(f"{tool_name}:{v}")
                    # also add prefix segments for directory-based rules like write:/etc
                    # allow entries may use short names like "write" or "write:/etc"
                    # we match by seeing if any allow entry is a prefix of candidates, via fnmatch
            # special: tool short aliases (write matches write_file, etc.)
            short = tool_name.split("_")[0]
            candidates.append(short)
            if args.get("path"):
                candidates.append(f"{short}:{args['path']}")

        # deny first
        for rule in self.deny:
            for cand in candidates:
                if _matches(rule, cand, tool_name, args):
                    return False, f"denied by rule '{rule}'"

        # if allow list is empty -> allow all (minus denials above)
        if not self.allow:
            return True, "allowed (no allowlist)"

        for rule in self.allow:
            for cand in candidates:
                if _matches(rule, cand, tool_name, args):
                    return True, f"allowed by rule '{rule}'"

        return False, f"not in allowlist {self.allow}"


def _matches(rule: str, candidate: str, tool_name: str, args: dict | None) -> bool:
    # exact
    if rule == candidate:
        return True
    # fnmatch on candidate
    if fnmatch.fnmatch(candidate, rule):
        return True
    # prefix match for directory rules: "write:/etc" should match "write_file:/etc/nginx/nginx.conf"
    # and "write:/etc/nginx/nginx.conf"
    if rule.endswith("*"):
        if fnmatch.fnmatch(candidate, rule):
            return True
    # allow entry like "exec" matching tool "exec"
    if rule == tool_name:
        return True
    # allow short alias prefix: "write:/etc" vs candidate "write_file:/etc/nginx/nginx.conf"
    # normalize by comparing after colon
    if ":" in rule and ":" in candidate:
        rule_tool, rule_path = rule.split(":", 1)
        cand_tool, cand_path = candidate.split(":", 1)
        # short alias: "write" matches "write_file"
        if rule_tool in cand_tool or cand_tool.startswith(rule_tool):
            if fnmatch.fnmatch(cand_path, rule_path) or cand_path.startswith(rule_path):
                return True
            if rule_path.startswith("/") and cand_path.startswith(rule_path):
                return True
    # bare tool prefix: allow "write" matches "write_file"
    if ":" in candidate and ":" not in rule:
        cand_tool = candidate.split(":")[0]
        if rule == cand_tool or cand_tool.startswith(rule) or rule in cand_tool:
            return True
    return False
