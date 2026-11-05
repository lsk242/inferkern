"""Checks runner tests."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inferkern.agent.goal import load_goal
from inferkern.agent.checks import run_checks


def test_all_goals_parse_and_checks_exist():
    for gy in sorted((ROOT / "goals").glob("*/goal.yaml")):
        goal = load_goal(gy)
        assert goal.name
        assert goal.max_steps > 0
        for p in goal.check_paths():
            assert p.exists(), f"{goal.name}: missing check {p}"
