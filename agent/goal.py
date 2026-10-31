"""Goal file parser — YAML/Markdown goal.md → structured Goal."""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

import yaml


@dataclasses.dataclass
class LLMConfig:
    endpoint: str | None = None  # e.g. https://api.openai.com/v1
    api_key: str | None = None  # resolved from env expansion
    model: str = "gpt-4o-mini"
    provider: str = "openai"  # openai | anthropic | mock
    local_model: str | None = None  # path to GGUF (future)


@dataclasses.dataclass
class Budget:
    max_steps: int = 60
    max_tokens: int = 200_000
    timeout_min: int = 30


@dataclasses.dataclass
class Constraints:
    allow: list[str] = dataclasses.field(default_factory=list)
    deny: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Goal:
    name: str
    description: str = ""
    llm: LLMConfig = dataclasses.field(default_factory=LLMConfig)
    budget: Budget = dataclasses.field(default_factory=Budget)
    constraints: Constraints = dataclasses.field(default_factory=Constraints)
    accept: list[str] = dataclasses.field(default_factory=list)  # check script paths relative to goal dir
    raw: dict = dataclasses.field(default_factory=dict)  # passthrough extras


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _expand_env(value: str) -> str:
    """Expand $VAR and ${VAR} using current environment."""
    return os.path.expandvars(value)


def _expand_env_deep(obj):
    if isinstance(obj, str):
        return _expand_env(obj)
    if isinstance(obj, dict):
        return {k: _expand_env_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_deep(v) for v in obj]
    return obj


def _parse_llm(d: dict | None) -> LLMConfig:
    if not d:
        return LLMConfig()
    d = _expand_env_deep(d)
    return LLMConfig(
        endpoint=d.get("endpoint"),
        api_key=d.get("api_key"),
        model=d.get("model", "gpt-4o-mini"),
        provider=d.get("provider", "openai"),
        local_model=d.get("local_model"),
    )


def _parse_budget(d: dict | None) -> Budget:
    if not d:
        return Budget()
    return Budget(
        max_steps=int(d.get("max_steps", 60)),
        max_tokens=int(d.get("max_tokens", 200_000)),
        timeout_min=int(d.get("timeout_min", 30)),
    )


def _parse_constraints(d: dict | None) -> Constraints:
    if not d:
        return Constraints()
    return Constraints(
        allow=list(d.get("allow", [])),
        deny=list(d.get("deny", [])),
    )


def _dict_to_goal(data: dict, description: str = "") -> Goal:
    return Goal(
        name=str(data.get("name", "unnamed")),
        description=description or str(data.get("description", "")),
        llm=_parse_llm(data.get("llm")),
        budget=_parse_budget(data.get("budget")),
        constraints=_parse_constraints(data.get("constraints")),
        accept=list(data.get("accept", [])),
        raw={k: v for k, v in data.items() if k not in {"name", "description", "llm", "budget", "constraints", "accept"}},
    )


def _looks_like_yaml(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("name:") or "name:" in stripped.splitlines()[0] if stripped else False


def load_goal(path: str | Path) -> Goal:
    """Load a goal file.

    Supported formats:
    - Pure YAML (``name: web-server`` …)
    - Markdown with YAML front-matter (``---`` fences)
    - Markdown without front-matter — first heading becomes name, rest is description
    """
    p = Path(path)
    text = p.read_text()

    # Front-matter?
    m = _FRONTMATTER_RE.match(text)
    if m:
        data = yaml.safe_load(m.group(1)) or {}
        description = text[m.end() :].strip()
        return _dict_to_goal(data, description=description)

    # Pure YAML?
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict) and "name" in data:
            return _dict_to_goal(data)
    except yaml.YAMLError:
        pass

    # Fallback: treat as plain markdown description
    heading = ""
    for line in text.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            break
    return Goal(name=heading or p.parent.name or "unnamed", description=text.strip())


def goal_dir(path: str | Path) -> Path:
    """Directory containing the goal file — used to resolve relative ``accept`` paths."""
    return Path(path).parent
