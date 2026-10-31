"""CLI entrypoint for the agent loop."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from agent.budget import BudgetTracker
from agent.goal import load_goal
from agent.journal import Journal, State
from agent.llm import create_provider
from agent.loop import AgentLoop
from agent.policy import PolicyGate
from agent.tools.registry import all_tools


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="inferkern agent — converge toward a goal")
    parser.add_argument("--goal", default="/etc/inferkern/goal.md", help="Path to goal file")
    parser.add_argument("--state-dir", default="/var/lib/inferkern", help="Persistent state directory")
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Parse goal and exit (no convergence)")
    parser.add_argument("--once", action="store_true", help="Single pass: checks only, no LLM (useful for CI)")
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("inferkern.main")

    goal_path = Path(args.goal)
    if not goal_path.exists():
        log.error("Goal file not found: %s", goal_path)
        sys.exit(2)

    goal = load_goal(goal_path)
    log.info("Goal: %s — %s", goal.name, goal.description[:200] if goal.description else "(no description)")

    if args.dry_run:
        log.info("Dry run — goal parsed successfully")
        log.info("  name: %s", goal.name)
        log.info("  llm provider: %s model: %s", goal.llm.provider, goal.llm.model)
        log.info("  budget: %s", goal.budget)
        log.info("  constraints: %s", goal.constraints)
        log.info("  accept: %s", goal.accept)
        sys.exit(0)

    if args.once:
        from agent.checks import all_passed, resolve_checks, run_checks
        from agent.goal import goal_dir

        resolved = resolve_checks(goal.accept, goal_dir(goal_path))
        results = run_checks(resolved)
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] {r.check}")
            if r.output:
                print(r.output)
        sys.exit(0 if all_passed(results) else 1)

    # Full convergence
    state_dir = Path(args.state_dir)
    journal = Journal(state_dir / "journal.jsonl")
    state = State(state_dir / "facts.json")
    budget = BudgetTracker(budget=goal.budget)
    policy = PolicyGate(goal.constraints)
    tools = all_tools()
    provider = create_provider(goal)

    loop = AgentLoop(goal=goal, goal_path=goal_path, provider=provider, tools=tools, journal=journal, state=state, budget=budget, policy=policy)
    converged = loop.run()
    sys.exit(0 if converged else 1)


if __name__ == "__main__":
    main()
