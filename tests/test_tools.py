import tempfile
from pathlib import Path

from agent.tools.registry import all_tools


def test_exec_success():
    tools = all_tools()
    r = tools.execute("exec", {"command": "echo hello"})
    assert r.ok
    assert "hello" in r.output


def test_exec_failure():
    tools = all_tools()
    r = tools.execute("exec", {"command": "false"})
    assert not r.ok


def test_write_and_read_file():
    with tempfile.TemporaryDirectory() as d:
        tools = all_tools(workdir=d)
        r = tools.execute("write_file", {"path": str(Path(d) / "test.txt"), "content": "hello world"})
        assert r.ok
        r2 = tools.execute("read_file", {"path": str(Path(d) / "test.txt")})
        assert r2.ok
        assert "hello world" in r2.output


def test_write_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as d:
        tools = all_tools()
        target = str(Path(d) / "a" / "b" / "c.txt")
        r = tools.execute("write_file", {"path": target, "content": "deep"})
        assert r.ok
        assert Path(target).exists()


def test_unknown_tool():
    tools = all_tools()
    r = tools.execute("nonexistent", {})
    assert not r.ok
    assert "unknown tool" in r.output


def test_list_dir():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "file1.txt").write_text("x")
        tools = all_tools()
        r = tools.execute("list_dir", {"path": d})
        assert r.ok
        assert "file1.txt" in r.output


def test_probe():
    tools = all_tools()
    r = tools.execute("probe", {"probe": "os"})
    assert r.ok
    assert len(r.output) > 0
