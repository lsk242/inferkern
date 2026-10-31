"""Goal file parser for /etc/inferkern/goal.md (and repo goals/<name>/goal.md).

Format is a small markdown+frontmatter mix. We support:
  # header
  name: <str>
  llm: { endpoint: $ENV_VAR, api_key: $ENV_VAR }  or inline dict/json-ish
  budget: { max_steps: N, max_tokens: N, timeout_min: N }
  accept: [checks/http-200.sh, ...]
  constraints:
    allow: [exec, apk, ...]
    deny: [mkfs:/dev/vda1, ...]
"""
from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path


@dataclasses.dataclass
class Budget:
    max_steps: int = 60
    max_tokens: int = 200000
    timeout_min: int = 30


@dataclasses.dataclass
class Goal:
    name: str
    budget: Budget
    accept: list[str]
    allow: list[str]
    deny: list[str]
    llm_endpoint: str | None
    llm_api_key: str | None
    raw: str
    goal_dir: Path | None = None


def _expand_env(s: str) -> str:
    # expand $VAR and ${VAR}
    return os.path.expandvars(s)


def _parse_inline_list(s: str) -> list[str]:
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    if not s.strip():
        return []
    parts = [p.strip().strip("'\"") for p in s.split(",")]
    return [p for p in parts if p]


def _parse_budget(s: str) -> Budget:
    b = Budget()
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    for kv in s.split(","):
        kv = kv.strip()
        if not kv or ":" not in kv:
            continue
        k, v = kv.split(":", 1)
        k = k.strip()
        v = v.strip().strip("'\"")
        try:
            iv = int(v)
        except ValueError:
            continue
        if k == "max_steps":
            b.max_steps = iv
        elif k == "max_tokens":
            b.max_tokens = iv
        elif k == "timeout_min":
            b.timeout_min = iv
    return b


def _parse_llm(s: str) -> tuple[str | None, str | None]:
    # s like { endpoint: $LLM_ENDPOINT, api_key: $LLM_API_KEY }
    e = None
    k = None
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    for kv in s.split(","):
        kv = kv.strip()
        if ":" not in kv:
            continue
        kk, vv = kv.split(":", 1)
        kk = kk.strip()
        vv = vv.strip().strip("'\"")
        vv = _expand_env(vv)
        if kk == "endpoint":
            e = vv or None
        elif kk == "api_key":
            k = vv or None
    return e, k


def parse_goal_text(text: str, goal_dir: Path | None = None) -> Goal:
    name = "unnamed"
    budget = Budget()
    accept: list[str] = []
    allow: list[str] = []
    deny: list[str] = []
    endpoint = _expand_env(os.environ.get("LLM_ENDPOINT", ""))
    api_key = _expand_env(os.environ.get("LLM_API_KEY", ""))
    # defaults: if env missing, None
    endpoint = endpoint or None
    api_key = api_key or None

    in_constraints = False
    in_accept_list = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        # continuation of YAML list for accept: (lines like "  - checks/http-200.sh")
        if in_accept_list:
            if line.startswith("- ") or line.startswith("-"):
                item = line[1:].strip().strip("'\"")
                if item:
                    accept.append(item)
                continue
            else:
                in_accept_list = False
        if indent == 0 and line.startswith("constraints:"):
            in_constraints = True
            in_accept_list = False
            continue
        if indent == 0 and ":" in line and not line.startswith("-"):
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("'\"")
                in_constraints = False
            elif line.startswith("budget:"):
                budget = _parse_budget(line.split(":", 1)[1].strip())
                in_constraints = False
            elif line.startswith("accept:"):
                val = line.split(":", 1)[1].strip()
                if val:
                    accept = _parse_inline_list(val)
                else:
                    in_accept_list = True
                in_constraints = False
            elif line.startswith("llm:"):
                e2, k2 = _parse_llm(line.split(":", 1)[1].strip())
                if e2:
                    endpoint = e2
                if k2:
                    api_key = k2
                in_constraints = False
            elif line.startswith("constraints:"):
                in_constraints = True
        elif in_constraints:
            if line.startswith("allow:"):
                allow = _parse_inline_list(line.split(":", 1)[1].strip())
            elif line.startswith("deny:"):
                deny = _parse_inline_list(line.split(":", 1)[1].strip())

    return Goal(
        name=name,
        budget=budget,
        accept=accept,
        allow=allow,
        deny=deny,
        llm_endpoint=endpoint,
        llm_api_key=api_key,
        raw=text,
        goal_dir=goal_dir,
    )


def load_goal(path: str | Path) -> Goal:
    p = Path(path)
    text = p.read_text()
    goal_dir = p.parent if p.is_file() else p
    return parse_goal_text(text, goal_dir=goal_dir)
