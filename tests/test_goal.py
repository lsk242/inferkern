import os
import tempfile
from pathlib import Path

from agent.goal import load_goal


def _write_tmp(content: str, suffix: str = ".yaml") -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_pure_yaml():
    p = _write_tmp("name: test-goal\nbudget:\n  max_steps: 10\naccept: [a.sh]\n")
    g = load_goal(p)
    assert g.name == "test-goal"
    assert g.budget.max_steps == 10
    assert g.accept == ["a.sh"]
    p.unlink()


def test_frontmatter():
    p = _write_tmp("---\nname: fm-goal\n---\nSome description here.\n", suffix=".md")
    g = load_goal(p)
    assert g.name == "fm-goal"
    assert "Some description" in g.description
    p.unlink()


def test_env_expansion():
    os.environ["TEST_GOAL_KEY"] = "secret123"
    p = _write_tmp("name: env-test\nllm:\n  api_key: $TEST_GOAL_KEY\n")
    g = load_goal(p)
    assert g.llm.api_key == "secret123"
    p.unlink()
    del os.environ["TEST_GOAL_KEY"]


def test_defaults():
    p = _write_tmp("name: minimal\n")
    g = load_goal(p)
    assert g.budget.max_steps == 60
    assert g.llm.provider == "openai"
    p.unlink()


def test_constraints():
    p = _write_tmp("name: c\nconstraints:\n  allow: [exec]\n  deny: [mkfs:/dev/sda]\n")
    g = load_goal(p)
    assert g.constraints.allow == ["exec"]
    assert g.constraints.deny == ["mkfs:/dev/sda"]
    p.unlink()
