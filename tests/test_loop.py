import tempfile
from pathlib import Path

from agent.budget import BudgetTracker
from agent.goal import Budget, Constraints, Goal, LLMConfig
from agent.journal import Journal, State
from agent.llm import MockProvider
from agent.loop import AgentLoop
from agent.policy import PolicyGate
from agent.tools.registry import all_tools


def _make_goal(tmpdir: str, accept: list[str] | None = None) -> Goal:
    return Goal(
        name="test-web-server",
        description="test goal",
        llm=LLMConfig(provider="mock"),
        budget=Budget(max_steps=20, max_tokens=50000, timeout_min=5),
        constraints=Constraints(allow=["exec", "read_file", "write_file", "list_dir", "check", "probe"]),
        accept=accept or [],
    )


def test_loop_converges_with_no_checks():
    """If no accept checks, loop should exhaust budget (no convergence criterion)."""
    with tempfile.TemporaryDirectory() as d:
        goal = _make_goal(d, accept=[])
        tools = all_tools(workdir=d)
        journal = Journal(Path(d) / "journal.jsonl")
        state = State(Path(d) / "facts.json")
        budget = BudgetTracker(budget=goal.budget)
        policy = PolicyGate(goal.constraints)
        provider = MockProvider(plan=[{"tool": "exec", "args": {"command": "echo hi"}}])

        # With empty accept, checks return None — loop runs until budget
        # This tests that the loop terminates
        goal.budget.max_steps = 3
        budget = BudgetTracker(budget=goal.budget)
        loop = AgentLoop(goal=goal, goal_path=Path(d) / "goal.yaml", provider=provider, tools=tools, journal=journal, state=state, budget=budget, policy=policy)
        result = loop.run()
        # Should not converge (no checks), but should terminate
        assert not result
        assert journal.entry_count() > 0


def test_loop_converges_when_checks_pass():
    """Loop converges immediately when checks already pass."""
    with tempfile.TemporaryDirectory() as d:
        # Create a check that always passes
        check_path = Path(d) / "pass.sh"
        check_path.write_text("#!/bin/sh\nexit 0\n")
        check_path.chmod(0o755)

        goal = _make_goal(d, accept=[str(check_path)])
        tools = all_tools(workdir=d)
        journal = Journal(Path(d) / "journal.jsonl")
        state = State(Path(d) / "facts.json")
        budget = BudgetTracker(budget=goal.budget)
        policy = PolicyGate(goal.constraints)
        provider = MockProvider(plan=[])

        loop = AgentLoop(goal=goal, goal_path=Path(d) / "goal.yaml", provider=provider, tools=tools, journal=journal, state=state, budget=budget, policy=policy)
        result = loop.run()
        assert result  # converged


def test_loop_mock_writes_file():
    """Mock provider writes a file, then check passes."""
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / "output.txt"
        check_path = Path(d) / "check.sh"
        check_path.write_text(f'#!/bin/sh\ntest -f "{target}"\n')
        check_path.chmod(0o755)

        goal = _make_goal(d, accept=[str(check_path)])
        tools = all_tools(workdir=d)
        journal = Journal(Path(d) / "journal.jsonl")
        state = State(Path(d) / "facts.json")
        budget = BudgetTracker(budget=goal.budget)
        policy = PolicyGate(goal.constraints)
        provider = MockProvider(plan=[{"tool": "write_file", "args": {"path": str(target), "content": "hello"}}])

        loop = AgentLoop(goal=goal, goal_path=Path(d) / "goal.yaml", provider=provider, tools=tools, journal=journal, state=state, budget=budget, policy=policy)
        result = loop.run()
        assert result
        assert target.exists()
