"""Unit tests for supervisor/sup.py — no root/QEMU required."""
import os
import sys
import signal
import time
import tempfile
import subprocess
import pathlib
import importlib.util
import unittest
from unittest import mock

# Import supervisor module
REPO = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("sup", str(REPO / "supervisor" / "sup.py"))
assert spec and spec.loader
sup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sup)


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            # Clear inferkern vars
            env = {k: v for k, v in os.environ.items() if not k.startswith("INFERKERN")}
            with mock.patch.dict(os.environ, env, clear=True):
                # Remove cmdline influence
                with mock.patch("builtins.open", side_effect=OSError("no proc")):
                    cfg = sup.Config()
                    self.assertEqual(cfg.max_restarts, 3)
                    self.assertIn("python3", cfg.agent_cmd[0])

    def test_env_overrides(self):
        with mock.patch.dict(os.environ, {"INFERKERN_MAX_RESTARTS": "5", "INFERKERN_AGENT_CMD": "echo hello"}, clear=False):
            with mock.patch("builtins.open", side_effect=OSError):
                cfg = sup.Config()
                self.assertEqual(cfg.max_restarts, 5)
                self.assertEqual(cfg.agent_cmd, ["echo", "hello"])


class TestReapZombies(unittest.TestCase):
    def test_reap_no_children(self):
        # No children — should return empty
        result = sup.reap_zombies()
        self.assertIsInstance(result, list)

    def test_reap_after_child_exit(self):
        proc = subprocess.Popen(["true"])
        proc.wait()
        # Give kernel a moment
        time.sleep(0.05)
        # The child was already waited — reap should be empty (waitpid(-1) with no zombies)
        # But if we fork a child and don't wait, reap should find it
        pid = os.fork()
        if pid == 0:
            os._exit(42)
        else:
            time.sleep(0.1)
            reaped = sup.reap_zombies()
            pids = [p for p, _ in reaped]
            self.assertIn(pid, pids)
            # Verify exit code
            for p, code in reaped:
                if p == pid:
                    self.assertEqual(code, 42)


class TestSpawnAgent(unittest.TestCase):
    def test_spawn_and_exit(self):
        with mock.patch.dict(os.environ, {"INFERKERN_AGENT_CMD": "true"}, clear=False):
            with mock.patch("builtins.open", side_effect=OSError):
                cfg = sup.Config()
                proc = sup.spawn_agent(cfg)
                rc = proc.wait(timeout=5)
                self.assertEqual(rc, 0)


class TestSyntax(unittest.TestCase):
    def test_supervisor_compiles(self):
        path = REPO / "supervisor" / "sup.py"
        with open(path) as f:
            source = f.read()
        compile(source, str(path), "exec")

    def test_scripts_syntax(self):
        for name in ["vm/build-rootfs.sh", "vm/create-disk.sh", "scripts/build-vm.sh", "scripts/run-qemu.sh"]:
            path = REPO / name
            if path.exists():
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{name} syntax error: {result.stderr}")

    def test_checks_executable(self):
        for check in (REPO / "goals" / "web-server" / "checks").glob("*.sh"):
            self.assertTrue(os.access(check, os.X_OK), f"{check} not executable")
            result = subprocess.run(["bash", "-n", str(check)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{check} syntax error: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
