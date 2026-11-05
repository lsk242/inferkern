"""Supervisor unit tests (mock-based, no root/QEMU needed — salvaged from PR #2 approach)."""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inferkern.supervisor.sup import Config


def test_config_defaults():
    cfg = Config()
    assert cfg.max_restarts >= 1
    assert cfg.restart_window_s > 0
    assert cfg.rescue in ("shell", "halt", "reboot")


def test_config_cmdline_override(tmp_path, monkeypatch):
    fake = tmp_path / "cmdline"
    fake.write_text("console=ttyS0 inferkern.max_restarts=7 inferkern.rescue=halt ro")
    with mock.patch("inferkern.supervisor.sup.Path") as MockPath:
        # Config reads Path("/proc/cmdline"); emulate by patching read via open path
        real_path = Path
        def fake_path(p):
            if str(p) == "/proc/cmdline":
                return fake
            return real_path(p)
        MockPath.side_effect = fake_path
        cfg = Config.__new__(Config)
        cfg.max_restarts = 3
        cfg.restart_window_s = 300
        cfg.rescue = "shell"
        cfg.goal_dir = "/etc/inferkern"
        cfg.state_dir = "/var/lib/inferkern"
        cfg._apply_cmdline()
    assert cfg.max_restarts == 7
    assert cfg.rescue == "halt"


def test_policy_decoy_tool_not_matched_by_substring():
    """Regression for PR #1 review: allow 'read' must not match 'read_evil'."""
    from inferkern.agent.policy import Policy

    pol = Policy(allow=["read_file"], deny=[])
    ok, _ = pol.is_allowed("read_evil", {"path": "/etc/passwd"})
    assert not ok
    ok2, _ = pol.is_allowed("read_file", {"path": "/etc/passwd"})
    assert ok2
