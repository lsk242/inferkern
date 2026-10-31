from agent.goal import Constraints
from agent.policy import PolicyGate


def test_allow_all_when_empty():
    gate = PolicyGate(Constraints(allow=[], deny=[]))
    ok, _ = gate.check("exec", {"command": "ls"})
    assert ok


def test_deny_wins():
    gate = PolicyGate(Constraints(allow=["exec"], deny=["exec:rm"]))
    ok, reason = gate.check("exec", {"command": "rm -rf /"})
    assert not ok
    assert "denied" in reason


def test_allowlist_blocks_unlisted():
    gate = PolicyGate(Constraints(allow=["exec"], deny=[]))
    ok, _ = gate.check("write_file", {"path": "/etc/passwd"})
    assert not ok


def test_write_path_matching():
    gate = PolicyGate(Constraints(allow=["write_file:/etc"], deny=[]))
    ok, _ = gate.check("write_file", {"path": "/etc/nginx/nginx.conf"})
    assert ok
    ok2, _ = gate.check("write_file", {"path": "/tmp/evil"})
    assert not ok2


def test_deny_path_prefix():
    gate = PolicyGate(Constraints(allow=["exec", "write_file"], deny=["write_file:/etc/shadow"]))
    ok, _ = gate.check("write_file", {"path": "/etc/shadow"})
    assert not ok
    ok2, _ = gate.check("write_file", {"path": "/etc/nginx/conf"})
    assert ok2
