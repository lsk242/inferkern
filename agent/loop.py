"""Main converge loop: observe -> LLM -> gate -> execute -> journal, steady-state reconcile."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time


def _log(msg: str):
    print(f"[agent] {msg}", flush=True)


def _load_goal(goal_path: str):
    from .goal import load_goal, Goal, Budget

    p = pathlib.Path(goal_path)
    if p.exists():
        return load_goal(p)
    # try defaults
    for cand in ["/etc/inferkern/goal.md", "goals/web-server/goal.md", "goals/web-server"]:
        cp = pathlib.Path(cand)
        if cp.exists():
            if cp.is_dir():
                cp = cp / "goal.md"
            if cp.exists():
                return load_goal(cp)
    # fallback: minimal goal
    _log(f"goal not found at {goal_path}, using fallback web-server goal")
    return Goal(
        name="web-server",
        budget=Budget(),
        accept=["checks/http-200.sh"],
        allow=["exec", "apk", "write:/etc", "write:/srv", "write:/var", "service", "probe", "read", "check", "journal"],
        deny=[],
        llm_endpoint=None,
        llm_api_key=None,
        raw="fallback web-server goal",
        goal_dir=pathlib.Path("goals/web-server") if pathlib.Path("goals/web-server").exists() else None,
    )


def _ensure_web_server_dry_actions(tools):
    """Deterministic fallback when LLM is in stub mode: converge to nginx + static site."""
    steps = []

    # 1. apk nginx if needed
    r = tools.dispatch("probe", kind="lsblk")
    # Check nginx installed
    r2 = tools.dispatch("exec", cmd="which nginx || echo MISSING")
    need_nginx = "MISSING" in (r2.output or "")

    if need_nginx:
        steps.append({"tool": "apk", "args": {"package": "nginx"}})

    # 2. write static site
    steps.append({"tool": "write", "args": {"path": "/srv/http/index.html", "content": INDEX_HTML}})
    steps.append({"tool": "write", "args": {"path": "/etc/nginx/http.d/default.conf", "content": NGINX_CONF}})

    # 3. ensure nginx running
    steps.append({"tool": "service", "args": {"name": "nginx", "action": "start"}})

    # 4. verify
    steps.append({"tool": "check", "args": {}})
    return steps


INDEX_HTML = """<!doctype html><html><head><meta charset=\"utf-8\"><title>inferkern</title></head><body><h1>inferkern web-server OK</h1><p>Converged by inferkern agent.</p></body></html>
"""

NGINX_CONF = """server {
    listen 80 default_server;
    root /srv/http;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
}
"""


def _parse_llm_actions(text: str) -> list[dict]:
    """Parse LLM JSON response into action list."""
    if not text or not text.strip():
        return []
    # Try to extract JSON block
    import re

    # find first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return []
    actions = obj.get("actions") or obj.get("steps") or []
    if isinstance(actions, dict):
        actions = [actions]
    norm = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        tool = a.get("tool") or a.get("name") or ""
        args = a.get("args") or a.get("arguments") or {}
        # unwrap if args nested oddly
        if not isinstance(args, dict):
            args = {}
        # normalize common aliases
        if tool in ("read_file", "read-file"):
            tool = "read"
        elif tool in ("write_file", "write-file"):
            tool = "write"
        elif tool == "run":
            tool = "exec"
        norm.append({"tool": tool, "args": args})
    return norm


def _run_actions(tools, actions: list[dict]) -> bool:
    ok_all = True
    for act in actions:
        tool = act.get("tool", "")
        args = act.get("args", {})
        if not tool:
            continue
        _log(f" -> {tool} {args}")
        res = tools.dispatch(tool, **args)
        _log(f"    {'ok' if res.ok else 'FAIL'}: {res.output[:300]}")
        if not res.ok and tool in ("apk", "write", "service", "exec"):
            ok_all = False
    return ok_all


def converge(goal_path: str = "", state_dir: str = "", max_steps_override: int | None = None):
    from .journal import Journal
    from .tools import ToolRegistry
    from .llm import LLMClient, build_prompt

    goal = _load_goal(goal_path or os.environ.get("INFERKERN_GOAL", "/etc/inferkern/goal.md"))
    state_dir = state_dir or os.environ.get("INFERKERN_STATE_DIR", "/var/lib/inferkern")
    pathlib.Path(state_dir).mkdir(parents=True, exist_ok=True)
    journal = Journal(pathlib.Path(state_dir) / "journal.jsonl")

    _log(f"goal: {goal.name} accept={goal.accept} allow={goal.allow}")
    _log(f"state_dir: {state_dir}")

    llm = LLMClient(endpoint=goal.llm_endpoint, api_key=goal.llm_api_key)
    if llm.is_stub:
        _log("WARN: LLM_API_KEY/LLM_ENDPOINT missing — running in stub/deterministic mode")

    tools = ToolRegistry(goal=goal, journal=journal, dry_run=False)

    # Quick check: already converged?
    chk = tools.dispatch("check")
    if chk.ok:
        _log("checks already passing — steady-state reconcile (one probe then exit 0)")
        # In Docker we exit; in steady-state loop we'd sleep and recheck
        if os.environ.get("INFERKERN_ONESHOT") == "1" or os.environ.get("INFERKERN_STEADY_EXIT") == "1":
            return 0
        # otherwise sleep briefly and re-verify then exit
        time.sleep(2)
        chk2 = tools.dispatch("check")
        _log(f"re-check: {'PASS' if chk2.ok else 'FAIL'}")
        return 0 if chk2.ok else 1

    max_steps = max_steps_override or goal.budget.max_steps
    _log(f"budget: max_steps={max_steps} max_tokens={goal.budget.max_tokens}")

    for step in range(1, max_steps + 1):
        # observe
        probe = tools.dispatch("probe", kind="all")
        facts = probe.output[:6000] if probe.output else ""
        history = "\n".join([__import__("json").dumps(e) for e in journal.tail(8)])

        # check before asking LLM — may have converged from prior step
        chk = tools.dispatch("check")
        if chk.ok:
            _log(f"step {step}: checks PASS — converged")
            # steady-state: one more reconcile then exit
            return 0

        _log(f"step {step}/{max_steps}: checks not yet passing, deciding next action...")

        if llm.is_stub:
            # Deterministic fallback: run fixed plan once, then verify
            if step == 1:
                actions = _ensure_web_server_dry_actions(tools)
                _log(f"stub mode: running {len(actions)} deterministic actions")
                _run_actions(tools, actions)
            else:
                # retry service start if needed
                r = tools.dispatch("exec", cmd="ss -tln 2>/dev/null | grep -q ':80 ' && echo LISTENING || echo NOTLISTENING")
                if "NOTLISTENING" in (r.output or ""):
                    tools.dispatch("service", name="nginx", action="start")
                # small wait and recheck
                time.sleep(1)
            continue

        # LLM path
        messages = build_prompt(goal, facts, history)
        res = llm.chat(messages)
        if res.error and not res.text:
            _log(f"LLM error: {res.error} — retry with backoff")
            time.sleep(min(2 * step, 10))
            continue
        if res.tokens_used:
            _log(f"LLM tokens this call: {res.tokens_used} total={llm.total_tokens}")
            if llm.total_tokens > goal.budget.max_tokens:
                _log("token budget exhausted — halting")
                journal.append({"event": "budget_exhausted", "tokens": llm.total_tokens})
                return 2
        actions = _parse_llm_actions(res.text)
        if not actions:
            _log(f"LLM returned no parseable actions, raw: {res.text[:400]}")
            continue
        _run_actions(tools, actions)

    # final check
    chk = tools.dispatch("check")
    if chk.ok:
        _log("converged within budget")
        return 0
    _log(f"FAILED to converge in {max_steps} steps; last check: {chk.output[:500]}")
    journal.append({"event": "failed_to_converge", "steps": max_steps})
    return 1


def main():
    import argparse

    p = argparse.ArgumentParser(description="inferkern agent loop")
    p.add_argument("--goal", default=os.environ.get("INFERKERN_GOAL", "/etc/inferkern/goal.md"))
    p.add_argument("--state-dir", default=os.environ.get("INFERKERN_STATE_DIR", "/var/lib/inferkern"))
    p.add_argument("--max-steps", type=int, default=None)
    args = p.parse_args()
    code = converge(goal_path=args.goal, state_dir=args.state_dir, max_steps_override=args.max_steps)
    sys.exit(code)


if __name__ == "__main__":
    main()
