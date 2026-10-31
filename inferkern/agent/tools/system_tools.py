"""System/discovery tools exposed to the LLM."""
from __future__ import annotations

import subprocess
import shutil


def probe(kind: str) -> dict:
    """Run a discovery probe. kind in: disks, net, mem, cpu, os, mounts, ports, packages, all."""
    from ..probes import collect_facts  # lazy to avoid cycle at import

    facts = collect_facts()
    kind = kind.lower().strip()
    if kind in ("all", "everything", ""):
        return {"facts": facts}
    if kind in facts:
        return {"probe": kind, "output": facts[kind]}
    # aliases
    aliases = {
        "disk": "disks",
        "network": "net",
        "memory": "mem",
        "storage": "disks",
    }
    k = aliases.get(kind)
    if k and k in facts:
        return {"probe": k, "output": facts[k]}
    return {"error": f"unknown probe '{kind}', valid: {list(facts.keys()) + ['all']}"}


def run_checks_tool(check: str = "") -> dict:
    """Run acceptance checks. If check name given, filter to that one."""
    import os
    from pathlib import Path

    goal_path = os.environ.get("INFERKERN_GOAL", "goals/web-server/goal.yaml")
    try:
        from ..goal import load_goal

        goal = load_goal(goal_path)
        from ..checks import run_checks, summary

        results = run_checks(goal)
        if check:
            results = [r for r in results if check in r.name or check in (r.path.name if r.path else "")]
        return {
            "goal": goal.name,
            "results": [{"name": r.name, "passed": r.passed, "output": r.output[:1000]} for r in results],
            "all_passed": all(r.passed for r in results) if results else False,
            "summary": summary(results),
        }
    except Exception as e:
        return {"error": str(e), "goal_path": goal_path}


def journal_tail(n: int = 30) -> dict:
    import os
    from pathlib import Path

    state_dir = os.environ.get("INFERKERN_STATE_DIR", "/var/lib/inferkern")
    journal_path = Path(state_dir) / "journal.jsonl"
    if not journal_path.exists():
        # also try local ./state
        alt = Path("state/journal.jsonl")
        if alt.exists():
            journal_path = alt
        else:
            return {"entries": [], "note": "no journal yet"}
    try:
        lines = journal_path.read_text().splitlines()
        entries = [l for l in lines if l.strip()][-n:]
        return {"entries": entries, "total": len(lines)}
    except Exception as e:
        return {"error": str(e)}


TOOLS = {
    "probe": (
        {
            "name": "probe",
            "description": "Discover system state. Kinds: disks, net, mem, cpu, os, mounts, ports, packages, all. Call early to understand the machine before acting.",
            "parameters": {
                "type": "object",
                "properties": {"kind": {"type": "string", "description": "Probe kind (disks|net|mem|cpu|os|mounts|ports|packages|all)", "default": "all"}},
                "required": ["kind"],
            },
        },
        lambda kind="all", **_: probe(kind),
    ),
    "run_checks": (
        {
            "name": "run_checks",
            "description": "Run goal acceptance checks (shell scripts). Returns pass/fail per check. Use to verify convergence.",
            "parameters": {
                "type": "object",
                "properties": {"check": {"type": "string", "description": "Optional filter: check name substring"}},
                "required": [],
            },
        },
        lambda check="", **_: run_checks_tool(check),
    ),
    "journal": (
        {
            "name": "journal",
            "description": "Read recent journal entries (your past actions and results).",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "Number of entries (default 30)", "default": 30}},
                "required": [],
            },
        },
        lambda n=30, **_: journal_tail(n),
    ),
}
