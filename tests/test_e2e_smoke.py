"""End-to-end smoke test: does the heuristic actually converge via real tools."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_smoke_convergence_real(tmp_path):
    """Run the smoke-test goal for real (writes to /tmp, starts http.server)."""
    import subprocess
    import os

    # Use a fresh state dir
    state_dir = tmp_path / "state"
    # Ensure no stale server
    subprocess.run("pkill -f 'http.server 8765' 2>/dev/null; sleep 0.1", shell=True)
    # Run agent
    env = os.environ.copy()
    env["INFERKERN_NO_LLM"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "inferkern.agent.loop", "goals/smoke-test/goal.yaml", "--no-llm", "--state-dir", str(state_dir), "--max-steps", "10"],
        capture_output=True, text=True, timeout=20, cwd=str(ROOT), env=env,
    )
    assert result.returncode == 0, f"agent failed: {result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    # Verify checks pass
    from inferkern.agent.goal import load_goal
    from inferkern.agent.checks import run_checks, all_passed

    goal = load_goal(ROOT / "goals/smoke-test/goal.yaml")
    checks = run_checks(goal)
    assert all_passed(checks), f"checks failed: {[(c.name, c.passed, c.output) for c in checks]}"
    # Cleanup
    subprocess.run("pkill -f 'http.server 8765' 2>/dev/null; sleep 0.1", shell=True)


def test_supervisor_oneshot_smoke(tmp_path):
    """Supervisor in oneshot mode should converge smoke-test and exit 0."""
    import subprocess, os

    subprocess.run("pkill -f 'http.server 8765' 2>/dev/null; sleep 0.1", shell=True)
    # Clean smoke state
    subprocess.run("rm -rf /tmp/inferkern-smoke 2>/dev/null", shell=True)
    state_dir = tmp_path / "sup-state"
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "inferkern.supervisor.sup", "goals/smoke-test/goal.yaml", "--state-dir", str(state_dir), "--oneshot"],
        capture_output=True, text=True, timeout=20, cwd=str(ROOT), env=env,
    )
    assert result.returncode == 0, f"supervisor failed: {result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    subprocess.run("pkill -f 'http.server 8765' 2>/dev/null; sleep 0.1", shell=True)
