"""Goal loading and validation (goal.yaml)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Goal:
    name: str
    description: str = ""
    # budget
    max_steps: int = 40
    max_tokens: int = 200_000  # approximate input+output budget
    timeout_min: int = 20
    # llm
    llm_endpoint: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # acceptance
    checks: list[str] = field(default_factory=list)
    # policy
    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)
    # raw
    raw: dict = field(default_factory=dict)
    goal_dir: Path = field(default_factory=lambda: Path("."))

    @property
    def checks_dir(self) -> Path:
        return self.goal_dir / "checks"

    def check_paths(self) -> list[Path]:
        """Resolved absolute check script paths (glob-aware)."""
        import glob as globmod

        paths: list[Path] = []
        for pattern in self.checks:
            # pattern is relative to goal_dir
            full = str(self.goal_dir / pattern) if not Path(pattern).is_absolute() else pattern
            for m in globmod.glob(full):
                paths.append(Path(m))
            # also try checks/<basename> if bare name
            if not globmod.glob(full):
                # keep literal for error reporting
                paths.append(Path(full))
        return paths


def _expand_env(s: str) -> str:
    """Expand $VAR and ${VAR} via os.environ."""
    return os.path.expandvars(s)


def load_goal(path: str | Path) -> Goal:
    """Load and validate a goal.yaml file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"goal file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"goal.yaml must be a mapping, got {type(data)}")

    name = data.get("name") or path.parent.name
    description = data.get("description", "")

    # budget
    budget = data.get("budget", {}) or {}
    max_steps = int(budget.get("max_steps", 40))
    max_tokens = int(budget.get("max_tokens", 200_000))
    timeout_min = int(budget.get("timeout_min", 20))

    # llm — allow env-var references like "$LLM_ENDPOINT" or plain strings; endpoint/key/model
    # may also be overridden by INFERKERN_LLM_* env vars at runtime (loop.py handles that)
    llm_cfg = data.get("llm", {}) or {}
    llm_endpoint = _expand_env(str(llm_cfg.get("endpoint", "")))
    llm_api_key = _expand_env(str(llm_cfg.get("api_key", "")))
    llm_model = _expand_env(str(llm_cfg.get("model", "")))

    # accept / checks — list of globs relative to goal dir
    accept = data.get("accept", data.get("checks", []))
    if isinstance(accept, str):
        accept = [accept]
    checks = [str(c) for c in (accept or [])]

    # constraints
    constraints = data.get("constraints", {}) or {}
    allow = [str(x) for x in constraints.get("allow", [])]
    deny = [str(x) for x in constraints.get("deny", [])]

    return Goal(
        name=name,
        description=description,
        max_steps=max_steps,
        max_tokens=max_tokens,
        timeout_min=timeout_min,
        llm_endpoint=llm_endpoint,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        checks=checks,
        allow=allow,
        deny=deny,
        raw=data,
        goal_dir=path.parent.resolve(),
    )
