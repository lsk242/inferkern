"""Agent convergence loop — the LLM-driven half of inferkern.

Loads goal.yaml + checks, gathers facts, then repeatedly asks the LLM for
tool calls until checks pass or budgets are exhausted.

Can also run in heuristic/dry-run mode without an LLM for testing.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from .checks import run_checks, all_passed, summary
from .goal import load_goal
from .llm import LLMClient, LLMConfig
from .policy import Policy
from .probes import collect_facts, facts_summary
from .state import State
from .tools import TOOL_HANDLERS, tool_definitions

console = Console()

SYSTEM_PROMPT = """You are inferkern — an autonomous Linux system administrator running as init.
Your job is to converge this machine to the declared goal (see below). You have tools to
discover state, install packages, write files, run commands, manage services, and verify checks.

Rules:
- Be systematic: probe first, then act, then verify. Don't guess blind.
- Be idempotent: every action must be safe to re-run (e.g. 'apk add nginx' not 'rm -rf /').
- Respect the policy allow/deny lists; if a tool is denied, explain and ask for guidance.
- After each action, check the result before deciding the next step.
- When all acceptance checks pass, reply with DONE and a summary.
- Be concise in reasoning; call tools aggressively — don't over-explain.

Tool use: call one or more tools per turn. After tool results, continue until done or blocked.
"""


def build_system_message(goal, facts_text: str) -> str:
    constraints_note = ""
    if goal.allow:
        constraints_note += f"\nAllowed tools: {goal.allow}"
    if goal.deny:
        constraints_note += f"\nDenied: {goal.deny}"
    checks_note = "\n".join(f"  - {p}" for p in goal.checks) if goal.checks else "  (none listed)"

    return (
        SYSTEM_PROMPT
        + f"\n## Goal: {goal.name}\n{goal.description}\n"
        + f"\n## Acceptance checks (must all pass):\n{checks_note}\n"
        + f"{constraints_note}\n"
        + f"\n## Machine facts (snapshot at boot):\n{facts_text}\n"
        + "\nBegin by probing if needed, then work toward passing checks."
    )


def execute_tool(name: str, arguments: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "tool": name, "arguments": arguments, "note": "dry-run: not executed"}
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool '{name}'", "available": sorted(TOOL_HANDLERS.keys())}
    try:
        result = handler(**arguments)
        if result is None:
            result = {"ok": True}
        if not isinstance(result, dict):
            result = {"output": str(result)}
        return result
    except Exception as e:
        return {"error": str(e), "tool": name, "traceback": traceback.format_exc()[:2000]}


def heuristic_plan(goal, state: State) -> list[tuple[str, dict]]:
    """Fallback planner when no LLM is configured — handles web-server via scripted steps.

    Returns list of (tool_name, arguments) tuples.
    """
    import subprocess as _sp

    # Check if nginx already installed/serving — if checks pass we are done
    try:
        from .checks import run_checks as _rc

        results = _rc(goal)
        if results and all(r.passed for r in results):
            return []
    except Exception:
        pass

    # Plan dispatch: smoke-test gets a Python-only path (no apt needed)
    goal_name = goal.name.lower()
    if goal_name == "smoke-test" or "smoke" in goal_name:
        steps_smoke: list[tuple[str, dict]] = []
        steps_smoke.append(("probe", {"kind": "all"}))
        steps_smoke.append((
            "write_file",
            {"path": "/tmp/inferkern-smoke/index.html",
             "content": "<!doctype html><html><head><title>inferkern smoke</title></head><body><h1>inferkern smoke — ok</h1><p>Goal: " + goal.name + "</p></body></html>\n"},
        ))
        steps_smoke.append(("exec", {"command": "mkdir -p /tmp/inferkern-smoke && cat /tmp/inferkern-smoke/index.html | head -5"}))
        # start Python http server on 8765 if not already listening
        steps_smoke.append(("exec", {"command": "ss -tlnp 2>&1 | grep -q ':8765 ' && echo 'already listening on 8765' || (nohup python3 -m http.server 8765 --directory /tmp/inferkern-smoke >/tmp/inferkern-smoke/server.log 2>&1 & sleep 0.5; echo started:$?; ss -tlnp 2>&1 | grep 8765 || echo 'no ss entry')"}))
        steps_smoke.append(("exec", {"command": "sleep 0.5; curl -sf http://127.0.0.1:8765/ 2>&1 | head -c 500; echo \"\"; echo smoke_curl:$?"}))
        steps_smoke.append(("run_checks", {}))
        return steps_smoke

    # Simple static plan for web-server goals (and demo-static)
    is_web = "web" in goal_name or "nginx" in goal_name or "http" in goal_name or "static" in goal_name

    steps: list[tuple[str, dict]] = []

    # Heuristic: for web goals, ensure nginx (install if missing), configure, start, verify
    # Don't skip just because binary exists — it may not be configured/running
    if is_web:
        steps.append(("probe", {"kind": "all"}))
        has_nginx = _sp.run("which nginx 2>/dev/null; nginx -v 2>&1", shell=True, capture_output=True, text=True).returncode == 0
        if not has_nginx:
            steps.append(("pkg_update", {}))
            steps.append(("pkg_install", {"packages": "nginx curl", "update": False}))
        steps.append(("write_file", {"path": "/srv/http/index.html", "content": "<!doctype html>\n<html><head><title>inferkern</title></head><body><h1>inferkern — it works</h1><p>Goal: " + goal.name + "</p></body></html>\n"}))
        # nginx config — write a minimal server block that serves /srv/http
        nginx_conf = """user nginx;
worker_processes 1;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/nginx/access.log;
    sendfile on;
    keepalive_timeout 65;
    server {
        listen 80 default_server;
        root /srv/http;
        index index.html;
        location / { try_files $uri $uri/ =404; }
    }
}
"""
        steps.append(("write_file", {"path": "/etc/nginx/nginx.conf", "content": nginx_conf}))
        steps.append(("exec", {"command": "mkdir -p /var/log/nginx /var/run && nginx -t 2>&1; echo nginx_conf_ok:$?"}))
        steps.append(("service_start", {"name": "nginx"}))
        steps.append(("exec", {"command": "sleep 1; curl -sf http://127.0.0.1/ 2>&1 | head -c 500; echo \"\"; echo curl_exit:$?"}))
        steps.append(("exec", {"command": "ss -tlnp 2>&1 | grep -q ':80 ' || (echo 'port 80 not listening, trying python fallback'; mkdir -p /srv/http; nohup python3 -m http.server 80 --directory /srv/http >/tmp/inferkern-pyhttp.log 2>&1 & sleep 0.5; curl -sf http://127.0.0.1/ 2>&1 | head -c 200; echo pyhttp:$?)"}))
        steps.append(("run_checks", {}))
        return steps

    # Generic fallback — just probe and run checks so we can report status
    return [("probe", {"kind": "all"}), ("run_checks", {})]


def run_loop(
    goal_path: str | Path,
    state_dir: str | Path | None = None,
    dry_run: bool = False,
    max_steps_override: int | None = None,
) -> int:
    """Main convergence loop. Returns 0 on success (checks pass), 1 otherwise."""
    goal = load_goal(goal_path)
    goal_dir = Path(goal.goal_dir)

    # state dir: env wins, else /var/lib/inferkern or ./state fallback
    if state_dir is None:
        state_dir = os.environ.get("INFERKERN_STATE_DIR", "")
        if not state_dir:
            # prefer writable location
            for cand in ("/var/lib/inferkern", "state"):
                p = Path(cand)
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    # test write
                    (p / ".writetest").write_text("ok")
                    (p / ".writetest").unlink(missing_ok=True)
                    state_dir = str(p)
                    break
                except Exception:
                    continue
            if not state_dir:
                state_dir = "state"
                Path(state_dir).mkdir(parents=True, exist_ok=True)

    state = State(state_dir)
    console.print(Panel(f"[bold]inferkern agent[/bold]  goal=[cyan]{goal.name}[/cyan]  state={state_dir}\n{goal.description}"))

    # discover LLM config
    llm_config = LLMConfig.from_env_and_goal(goal)
    llm_client: LLMClient | None = None
    if llm_config and not os.environ.get("INFERKERN_NO_LLM"):
        llm_client = LLMClient(llm_config)
        console.print(f"[dim]LLM: {llm_config.model} @ {llm_config.endpoint}[/dim]")
    else:
        if dry_run is False and os.environ.get("INFERKERN_FORCE_LLM"):
            console.print("[red]INFERKERN_FORCE_LLM set but no LLM endpoint — aborting[/red]")
            return 1
        console.print("[yellow]No LLM configured — using heuristic planner (set INFERKERN_LLM_ENDPOINT to use a model)[/yellow]")

    if os.environ.get("INFERKERN_DRY_RUN", "").lower() in ("1", "true", "yes"):
        dry_run = True
        console.print("[yellow]DRY RUN: tools will not execute[/yellow]")

    policy = Policy.from_goal(goal)

    max_steps = max_steps_override if max_steps_override is not None else goal.max_steps
    env_max = os.environ.get("INFERKERN_MAX_STEPS")
    if env_max:
        try:
            max_steps = int(env_max)
        except Exception:
            pass

    timeout_s = goal.timeout_min * 60
    env_timeout = os.environ.get("INFERKERN_TIMEOUT_MIN")
    if env_timeout:
        try:
            timeout_s = int(env_timeout) * 60
        except Exception:
            pass

    start_time = time.time()
    facts = collect_facts()
    facts_text = facts_summary(facts)
    state.update_facts({"last_boot_facts": {k: (v[:500] if isinstance(v, str) else str(v)[:500]) for k, v in facts.items()}})
    state.append({"event": "boot", "goal": goal.name, "facts_summary": facts_text[:2000]})

    # initial check — maybe already converged
    check_results = run_checks(goal)
    if all_passed(check_results):
        console.print("[green]All checks already pass — nothing to do.[/green]")
        console.print(summary(check_results))
        state.append({"event": "checks_pass_early", "summary": summary(check_results)})
        return 0
    else:
        console.print("[dim]Initial checks:[/dim]\n" + summary(check_results))

    # Build LLM conversation history
    messages: list[dict] = []
    if llm_client:
        messages.append({"role": "system", "content": build_system_message(goal, facts_text)})
        messages.append({"role": "user", "content": f"Goal '{goal.name}': {goal.description}\nInitial check results:\n{summary(check_results)}\n\nYour turn — call tools to converge the system. Start with a probe if you need more info."})

    tool_schemas = tool_definitions()
    total_tokens = 0
    step = 0

    # For non-LLM (heuristic) mode, pre-compute plan and execute it step-by-step
    heuristic_steps: list[tuple[str, dict]] | None = None
    heuristic_idx = 0
    if llm_client is None:
        heuristic_steps = heuristic_plan(goal, state)
        if not heuristic_steps:
            console.print("[yellow]Heuristic planner: no steps (checks may already pass)[/yellow]")
        else:
            console.print(f"[dim]Heuristic plan: {len(heuristic_steps)} steps[/dim]")

    while step < max_steps:
        if time.time() - start_time > timeout_s:
            console.print(f"[red]Timeout after {timeout_s}s ({goal.timeout_min} min) at step {step}[/red]")
            state.append({"event": "timeout", "step": step})
            break

        step += 1
        console.print(f"\n[bold]--- step {step}/{max_steps} ---[/bold]")

        # --- get next actions (LLM or heuristic) ---
        tool_calls: list[dict] = []
        assistant_text = ""

        if llm_client:
            try:
                resp = llm_client.chat(messages, tools=tool_schemas)
                assistant_text = resp.content or ""
                tool_calls = resp.tool_calls
                usage = resp.usage or {}
                total_tokens += int(usage.get("total_tokens") or usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0) or 0)
                if assistant_text:
                    console.print(f"[dim]LLM: {assistant_text[:600]}[/dim]")
                if resp.tool_calls:
                    console.print(f"[dim]LLM tool_calls: {[c['name'] for c in resp.tool_calls]}[/dim]")
                # budget check on tokens
                if goal.max_tokens and total_tokens >= goal.max_tokens:
                    console.print(f"[red]Token budget exhausted: {total_tokens} >= {goal.max_tokens}[/red]")
                    state.append({"event": "token_budget_exhausted", "tokens": total_tokens, "max": goal.max_tokens})
                    break
                # check for DONE signal without tool calls
                if not tool_calls and assistant_text:
                    upper = assistant_text.upper()
                    if "DONE" in upper and ("PASS" in upper or "CONVERGED" in upper or "COMPLETE" in upper or "ALL CHECKS" in upper):
                        # verify
                        check_results = run_checks(goal)
                        if all_passed(check_results):
                            console.print("[green]LLM declared DONE and checks pass![/green]")
                            return 0
                        else:
                            console.print("[yellow]LLM declared DONE but checks still fail — continuing[/yellow]\n" + summary(check_results))
                    elif not tool_calls:
                        # model chatted without calling tools — nudge it
                        console.print("[yellow]No tool calls this turn; nudging model[/yellow]")
                        messages.append({"role": "assistant", "content": assistant_text})
                        messages.append({"role": "user", "content": "You must call tools to make progress. If checks already pass, say DONE. Otherwise, call the next tool (probe, pkg_install, write_file, service_start, etc.)."})
                        continue
            except Exception as e:
                console.print(f"[red]LLM error: {e}[/red]")
                state.append({"event": "llm_error", "error": str(e)[:1000], "step": step})
                # retry with backoff or switch to heuristic
                if step > 3:
                    console.print("[yellow]Too many LLM errors — falling back to heuristic[/yellow]")
                    llm_client = None
                    heuristic_steps = heuristic_plan(goal, state)
                    heuristic_idx = 0
                    continue
                messages.append({"role": "user", "content": f"LLM error: {e}. Retry — call tools again."})
                continue
        else:
            # heuristic
            if heuristic_steps is None or heuristic_idx >= len(heuristic_steps):
                # no more planned steps — check if done
                check_results = run_checks(goal)
                if all_passed(check_results):
                    console.print("[green]All checks passed (heuristic)![/green]")
                    console.print(summary(check_results))
                    return 0
                else:
                    # try one more probe + report
                    console.print("[yellow]Heuristic plan exhausted — checks:[/yellow]\n" + summary(check_results))
                    break
            name, args = heuristic_steps[heuristic_idx]
            heuristic_idx += 1
            tool_calls = [{"id": f"heur-{step}", "name": name, "arguments": args}]
            assistant_text = f"[heuristic step {heuristic_idx}/{len(heuristic_steps)}]"

        if not tool_calls:
            console.print("[dim]No tool calls — idle step[/dim]")
            continue

        # --- policy gate + execution ---
        tool_results: list[dict] = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("arguments") or {}
            # policy check
            allowed, reason = policy.is_allowed(name, args)
            if not allowed:
                console.print(f"[red]Policy denied {name}({args}) — {reason}[/red]")
                result = {"error": f"policy denied: {reason}", "tool": name, "policy_denied": True}
                state.append({"event": "policy_denied", "tool": name, "args": args, "reason": reason, "step": step})
            else:
                console.print(f"[cyan]→ {name}[/cyan]({json.dumps(args)[:300]})")
                result = execute_tool(name, args, dry_run=dry_run)
                out_snip = json.dumps(result, ensure_ascii=False)[:600]
                console.print(f"  [dim]{out_snip}[/dim]")
                state.append({"event": "tool", "step": step, "tool": name, "args": args, "result": _truncate_result(result)})

            tool_results.append({"tool_call_id": tc.get("id", ""), "name": name, "result": result})

        # --- feed results back to LLM ---
        if llm_client:
            # add assistant + tool results
            messages.append({"role": "assistant", "content": assistant_text or "", "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in tool_calls]})
            for tr in tool_results:
                messages.append({"role": "tool", "tool_call_id": tr["tool_call_id"], "content": json.dumps(tr["result"], ensure_ascii=False)[:4000]})
            # also add a user nudge with latest check status every few steps
            if step % 4 == 0 or any(tr["result"].get("policy_denied") for tr in tool_results):
                check_results = run_checks(goal)
                messages.append({"role": "user", "content": f"Check status after step {step}:\n{summary(check_results)}\nContinue converging."})

        # --- periodic check (every step in heuristic mode, every 3 in LLM mode) ---
        check_interval = 1 if llm_client is None else 3
        if step % check_interval == 0 or step == max_steps:
            check_results = run_checks(goal)
            if all_passed(check_results):
                console.print("\n[bold green]✓ All checks passed![/bold green]")
                console.print(summary(check_results))
                state.append({"event": "converged", "step": step, "summary": summary(check_results)})
                return 0
            else:
                console.print(f"\n[dim]Checks after step {step}:[/dim]\n" + summary(check_results))

    # exhausted
    check_results = run_checks(goal)
    if all_passed(check_results):
        console.print("[green]Checks passed at budget edge — success[/green]")
        return 0
    console.print(f"\n[bold red]Did not converge in {step} steps / {time.time()-start_time:.1f}s[/bold red]")
    console.print(summary(check_results))
    state.append({"event": "exhausted", "step": step, "summary": summary(check_results) if check_results else "no checks ran"})
    return 1


def _truncate_result(result: dict, limit: int = 2000) -> dict:
    """Truncate large fields for journal (keep log small)."""
    out: dict = {}
    for k, v in result.items():
        if isinstance(v, str) and len(v) > limit:
            out[k] = v[:limit] + f"...[truncated {len(v)-limit} chars]"
        else:
            out[k] = v
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="inferkern agent loop")
    ap.add_argument("goal", nargs="?", default=os.environ.get("INFERKERN_GOAL", "goals/web-server/goal.yaml"), help="Path to goal.yaml")
    ap.add_argument("--state-dir", default=os.environ.get("INFERKERN_STATE_DIR", ""), help="State directory (default /var/lib/inferkern or ./state)")
    ap.add_argument("--dry-run", action="store_true", help="Don't execute tools")
    ap.add_argument("--max-steps", type=int, default=None, help="Override goal max_steps")
    ap.add_argument("--no-llm", action="store_true", help="Force heuristic mode (no LLM even if configured)")
    args = ap.parse_args()

    if args.no_llm:
        os.environ["INFERKERN_NO_LLM"] = "1"

    # handle signals gracefully
    def _sigterm(*_a):
        console.print("\n[yellow]Received SIGTERM — exiting[/yellow]")
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, _sigterm)
    # Ensure subprocess.wait() works correctly even if parent (PID1 supervisor) set SIGCHLD to SIG_IGN
    # SIG_IGN is inherited and breaks waitpid — must reset to DFL in the agent.
    try:
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    except Exception:
        pass

    sys.exit(run_loop(args.goal, state_dir=args.state_dir or None, dry_run=args.dry_run, max_steps_override=args.max_steps))


if __name__ == "__main__":
    main()
