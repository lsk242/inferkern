import pathlib
import tempfile
from agent.goal import Goal, Budget
from agent.journal import Journal
from agent.tools import ToolRegistry

def _goal(tmp_path):
    return Goal(
        name="test",
        budget=Budget(),
        accept=[],
        allow=["exec", "read", "write:/tmp", "apk", "probe", "service", "check", "journal"],
        deny=[],
        llm_endpoint=None,
        llm_api_key=None,
        raw="test",
        goal_dir=pathlib.Path("goals/web-server") if pathlib.Path("goals/web-server").exists() else None,
    )

def test_write_and_read(tmp_path):
    g = _goal(tmp_path)
    j = Journal(tmp_path / "j.jsonl")
    t = ToolRegistry(g, j)
    p = str(tmp_path / "hello.txt")
    # need allow for /tmp path
    g.allow = [f"write:{p}", "read", "write:/tmp"]
    t2 = ToolRegistry(g, j)
    r = t2.dispatch("write", path=p, content="hi")
    assert r.ok
    r = t2.dispatch("read", path=p)
    assert r.ok and "hi" in r.output

def test_exec():
    g = Goal("x", Budget(), [], ["exec"], [], None, None, "x", None)
    t = ToolRegistry(g, None)
    r = t.dispatch("exec", cmd="echo hello")
    assert r.ok and "hello" in r.output

def test_probe():
    g = Goal("x", Budget(), [], ["probe"], [], None, None, "x", None)
    t = ToolRegistry(g, None)
    r = t.dispatch("probe", kind="df")
    assert r.ok

def test_policy_deny():
    g = Goal("x", Budget(), [], ["read"], ["exec"], None, None, "x", None)
    t = ToolRegistry(g, Journal("/tmp/inferkern-test-journal.jsonl"))
    r = t.dispatch("exec", cmd="echo hi")
    assert not r.ok
