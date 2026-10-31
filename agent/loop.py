"""Main convergence loop — the agent's brain."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from agent.budget import BudgetTracker
from agent.checks import all_passed, resolve_checks, run_checks
from agent.goal import Goal, goal_dir
from agent.journal import Journal, State
from agent.llm import LLMProvider
from agent.policy import PolicyGate
from agent.tools.registry import ToolRegistry

log = logging.getLogger("inferkern.agent")


SYSTEM_PROMPT = """\
You are the inferkern agent. You run inside a minimal Linux system and your job is to \
converge the machine toward a declared goal.

You have tools to execute shell commands, read/write files, list directories, \
run discovery probes, and run acceptance checks.

Rules:
- Be systematic: probe first, then act
- Prefer idempotent commands (apk add, mkdir -p)
- After making changes, verify they worked
- If the goal is already met, say so and take no unnecessary actions
- Do not run destructive commands (mkfs, dd, rm -rf /) unless the goal explicitly requires it
- Keep actions minimal — one or two tool calls per step
"""


def _build_messages(goal: Goal, journal_tail: str, check_results: list | None, facts: dict) -> list[dict[str, Any]]:
    goal_text = f"# Goal: {goal.name}\n\n{goal.description}\n\nAccept checks: {goal.accept}"
    ctx_parts = [f"Goal:\n{goal_text}"]
    if facts:
        ctx_parts.append(f"Known facts:\n{facts}")
    if check_results is not None:
        lines = []
        for r in check_results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] {r.check}: {r.output[:300]}")
        ctx_parts.append("Acceptance check results:\n" + "\n".join(lines))
    if journal_tail:
        ctx_parts.append(f"Recent journal:\n{journal_tail}")

    user_content = "\n\n".join(ctx_parts)
    user_content += "\n\nWhat is the next action to converge toward the goal? Use tools to act."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _tool_results_to_messages(
    tool_calls: list, results: list, base_messages: list[dict]
) -> list[dict]:
    """Append assistant tool_call + tool result messages for next iteration."""
    msgs = list(base_messages)
    # Assistant message with tool calls
    msgs.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": tc.call_id or f"call_{i}", "type": "function", "function": {"name": tc.tool, "arguments": str(tc.args)}} for i, tc in enumerate(tool_calls)],
        }
    )
    for tc, res in zip(tool_calls, results):
        msgs.append({"role": "tool", "tool_call_id": tc.call_id or "call_0", "content": res.to_text()})
    return msgs


class AgentLoop:
    """Convergence loop: check → ask LLM → act → journal → repeat."""

    def __init__(
        self,
        goal: Goal,
        goal_path: str | Path,
        provider: LLMProvider,
        tools: ToolRegistry,
        journal: Journal,
        state: State,
        budget: BudgetTracker,
        policy: PolicyGate,
        check_timeout: int = 30,
    ):
        self.goal = goal
        self.goal_path = Path(goal_path)
        self.provider = provider
        self.tools = tools
        self.journal = journal
        self.state = state
        self.budget = budget
        self.policy = policy
        self.check_timeout = check_timeout
        self._messages: list[dict[str, Any]] | None = None

    def _run_checks(self):
        if not self.goal.accept:
            return None
        resolved = resolve_checks(self.goal.accept, goal_dir(self.goal_path))
        return run_checks(resolved, timeout=self.check_timeout)

    def run(self) -> bool:
        """Run until converged or budget exhausted. Returns True if converged."""
        log.info("Starting convergence loop for goal '%s' (provider: %s)", self.goal.name, self.provider.name)
        log.info("Budget: %s", self.budget.summary())
        self.journal.append("loop_start", goal=self.goal.name, provider=self.provider.name, budget=str(self.budget.budget))

        converged = False

        while True:
            # Budget check
            reason = self.budget.exhausted()
            if reason:
                log.warning("Budget exhausted: %s", reason)
                self.journal.append("budget_exhausted", reason=reason, summary=self.budget.summary())
                break

            # Run acceptance checks
            check_results = self._run_checks()
            if check_results is not None:
                for r in check_results:
                    log.info("  check %s: %s", r.check, "PASS" if r.passed else "FAIL")
                if all_passed(check_results):
                    log.info("All checks passed — converged!")
                    self.journal.append("converged", checks=[r.check for r in check_results])
                    converged = True
                    break

            # Build LLM context
            facts = self.state.all()
            journal_tail = self.journal.tail_text(n=30)

            if self._messages is None:
                messages = _build_messages(self.goal, journal_tail, check_results, facts)
            else:
                # Rebuild with fresh context each iteration (simpler than incremental)
                messages = _build_messages(self.goal, journal_tail, check_results, facts)
                # Carry forward conversation history for tool-calling models (keep last exchange)
                # For mock provider this doesn't matter; for real LLMs we keep full history
                if len(self._messages) > 2:
                    messages.extend(self._messages[2:])

            tool_schemas = self.tools.describe_for_llm()

            # Ask LLM
            try:
                response = self.provider.chat(messages, tools=tool_schemas)
            except Exception as e:
                log.error("LLM call failed: %s", e)
                self.journal.append("llm_error", error=str(e))
                break

            tokens = response.usage.get("input_tokens", 0) + response.usage.get("output_tokens", 0)
            self.budget.record_step(tokens=tokens)

            if response.content:
                log.info("LLM: %s", response.content[:500])

            if not response.tool_calls:
                log.info("LLM returned no tool calls — treating as done/thinking")
                self.journal.append("llm_no_action", content=response.content)
                # If checks already pass we'd have exited above; otherwise continue
                # Give it one more iteration to see if model converges
                self._messages = messages + [{"role": "assistant", "content": response.content or ""}]
                # Avoid infinite loop if model keeps returning nothing
                if self.budget.remaining_steps() <= 0:
                    break
                time.sleep(0.5)
                continue

            # Policy gate
            allowed_calls = []
            for tc in response.tool_calls:
                ok, reason = self.policy.check(tc.tool, tc.args)
                if not ok:
                    log.warning("Policy blocked %s: %s", tc.tool, reason)
                    self.journal.append("policy_blocked", tool=tc.tool, args=tc.args, reason=reason)
                else:
                    allowed_calls.append(tc)

            if not allowed_calls:
                log.warning("All tool calls blocked by policy")
                self._messages = messages
                continue

            # Execute
            results = []
            for tc in allowed_calls:
                log.info("→ %s %s", tc.tool, str(tc.args)[:300])
                result = self.tools.execute(tc.tool, tc.args)
                log.info("  ← %s", result.to_text()[:500])
                self.journal.append("tool_result", tool=tc.tool, args=tc.args, ok=result.ok, output=result.output[:2000])
                results.append(result)

            # Build next messages with tool results
            self._messages = _tool_results_to_messages(allowed_calls, results, messages)

            # Check convergence after acting (next iteration will re-check)

        self.journal.append("loop_end", converged=converged, summary=self.budget.summary())
        log.info("Loop ended: converged=%s budget=%s", converged, self.budget.summary())
        return converged
