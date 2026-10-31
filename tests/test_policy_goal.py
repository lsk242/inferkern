"""Tests for policy, goal loading, state, and loop dry-run."""
import os
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys_path_added = False
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inferkern.agent.goal import load_goal
from inferkern.agent.policy import Policy
from inferkern.agent.state import State


def test_goal_load_web_server():
    goal = load_goal(ROOT / "goals/web-server/goal.yaml")
    assert goal.name == "web-server"
    assert len(goal.checks) == 2
    assert goal.max_steps > 0
    # allowlist contains probe/exec etc.
    assert "probe" in goal.allow


def test_goal_env_expansion():
    os.environ["TEST_ENDPOINT"] = "https://example.com/v1"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "goal.yaml"
        p.write_text("name: test\nllm:\n  endpoint: $TEST_ENDPOINT\n  api_key: sk-test\naccept: []\n")
        goal = load_goal(p)
        assert goal.llm_endpoint == "https://example.com/v1"
    del os.environ["TEST_ENDPOINT"]


def test_policy_allow_all_when_empty():
    pol = Policy(allow=[], deny=[])
    ok, _ = pol.is_allowed("exec", {"command": "ls"})
    assert ok


def test_policy_deny_wins():
    pol = Policy(allow=["exec"], deny=["exec"])
    ok, _ = pol.is_allowed("exec", {"command": "ls"})
    assert not ok


def test_policy_allow_specific():
    pol = Policy(allow=["probe", "exec", "read_file"], deny=[])
    ok, _ = pol.is_allowed("probe", {"kind": "all"})
    assert ok
    ok, _ = pol.is_allowed("pkg_install", {"packages": "nginx"})
    assert not ok  # not in allowlist


def test_policy_path_based():
    pol = Policy(allow=["write_file:/etc", "read_file"], deny=["write_file:/etc/shadow"])
    ok, _ = pol.is_allowed("write_file", {"path": "/etc/nginx/nginx.conf"})
    assert ok
    ok2, _ = pol.is_allowed("write_file", {"path": "/etc/shadow"})
    assert not ok2


def test_state_journal():
    with tempfile.TemporaryDirectory() as td:
        s = State(td)
        s.append({"event": "test", "x": 1})
        s.append({"event": "test2", "x": 2})
        entries = s.read()
        assert len(entries) == 2
        assert entries[0]["x"] == 1
        assert s.journal_text().strip() != ""


def test_state_facts():
    with tempfile.TemporaryDirectory() as td:
        s = State(td)
        s.set_fact("foo", "bar")
        assert s.facts["foo"] == "bar"
        # reload
        s2 = State(td)
        assert s2.facts["foo"] == "bar"
