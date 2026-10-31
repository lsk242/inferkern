"""inferkern-sup — deterministic PID 1 supervisor.

Runs as init (``init=/sbin/inferkern``). Responsibilities:
- Mount /proc, /sys, /dev, /tmp, /run
- Bring up networking (DHCP on available interfaces)
- Mount goal + state volumes (virtio-9p, vfat, or tmpfs fallback)
- Spawn the agent loop, reap zombies, restart on failure
- Rescue shell after N failures

Designed to be testable without QEMU: in Docker/container mode it skips
mounts that require privilege and proceeds directly to agent spawn.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("inferkern.sup")


# ---------------------------------------------------------------------------
# Early boot helpers
# ---------------------------------------------------------------------------


def _run(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    log.info("sup: %s", cmd)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        log.debug("  stdout: %s", result.stdout.strip()[:500])
    if result.stderr:
        log.debug("  stderr: %s", result.stderr.strip()[:500])
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {cmd}\n{result.stderr}")
    return result


def _is_container() -> bool:
    """Detect container environment — skip privileged mounts there."""
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text()
        if "docker" in cgroup or "kubepods" in cgroup or "containerd" in cgroup:
            return True
    except OSError:
        pass
    # PID 1 in container is not the real init; check if we can mount
    return os.getpid() != 1


def mount_pseudofs():
    """Mount /proc, /sys, /dev — no-ops if already mounted or unprivileged."""
    if _is_container():
        log.info("Container detected — skipping pseudofs mounts")
        return
    for cmd in [
        "mount -t proc none /proc 2>&1 || true",
        "mount -t sysfs none /sys 2>&1 || true",
        "mount -t devtmpfs none /dev 2>&1 || mount --bind /dev /dev 2>&1 || true",
        "mkdir -p /run /tmp && mount -t tmpfs tmpfs /run 2>&1 || true",
        "mkdir -p /proc/sys/kernel 2>&1 || true",
    ]:
        _run(cmd)


def bring_up_network():
    """Try DHCP on available interfaces. Non-fatal if it fails."""
    if _is_container():
        log.info("Container — skipping network setup (host network assumed)")
        return
    # Try udhcpc (Alpine/BusyBox), dhcpcd, dhclient in order
    for cmd in [
        "udhcpc -i eth0 2>&1 || udhcpc -i enp0s3 2>&1 || true",
        "ip addr 2>&1 || ifconfig 2>&1 || true",
    ]:
        r = _run(cmd)
        if r.stdout:
            log.info("network: %s", r.stdout.strip()[:500])


def mount_volumes(goal_src: str | None = None, state_src: str | None = None):
    """Mount goal/state volumes. Tries 9p, vfat, virtiofs; falls back to tmpfs."""
    mounts = [
        (goal_src, "/etc/inferkern"),
        (state_src, "/var/lib/inferkern"),
    ]
    for src, dst in mounts:
        Path(dst).mkdir(parents=True, exist_ok=True)
        if not src:
            log.info("No source for %s — using existing dir", dst)
            continue
        # Try 9p first (QEMU -virtfs), then vfat (disk image)
        for fstype in ["9p", "virtiofs", "vfat", "ext4"]:
            opts = "trans=virtio,version=9p2000.L" if fstype == "9p" else ""
            opt_flag = f"-o {opts}" if opts else ""
            r = _run(f"mount -t {fstype} {opt_flag} {src} {dst} 2>&1 || true")
            if r.returncode == 0 and Path(dst).exists():
                # Verify mount actually has content
                if any(Path(dst).iterdir()):
                    log.info("Mounted %s -> %s (%s)", src, dst, fstype)
                    break
        else:
            log.warning("Could not mount %s -> %s, using %s as-is", src, dst, dst)


# ---------------------------------------------------------------------------
# Process supervision
# ---------------------------------------------------------------------------

# Children we track for reaping
_children: dict[int, str] = {}


def _handle_sigchld(signum, frame):
    """Reap zombie children."""
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            name = _children.pop(pid, f"pid={pid}")
            log.info("Reaped %s (pid %d) status %d", name, pid, status)
        except ChildProcessError:
            break


def spawn_agent(goal_path: str, state_dir: str, extra_args: list[str] | None = None) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "agent.main", "--goal", goal_path, "--state-dir", state_dir]
    if extra_args:
        cmd.extend(extra_args)
    log.info("Spawning agent: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd)
    _children[proc.pid] = "agent"
    return proc


# ---------------------------------------------------------------------------
# Main supervisor loop
# ---------------------------------------------------------------------------


def supervisor_main(args: argparse.Namespace) -> int:
    log.info("=" * 60)
    log.info("inferkern-sup starting (pid=%d)", os.getpid())
    log.info("goal=%s state=%s max_restarts=%d", args.goal, args.state_dir, args.max_restarts)
    log.info("=" * 60)

    # Early boot
    if not args.no_boot_setup:
        mount_pseudofs()
        bring_up_network()
        mount_volumes(args.goal_src, args.state_src)
    else:
        log.info("Skipping boot setup (--no-boot-setup)")

    # Ensure state dir exists
    Path(args.state_dir).mkdir(parents=True, exist_ok=True)

    # Signal handling for reaping (only useful as real PID 1)
    if os.getpid() == 1:
        signal.signal(signal.SIGCHLD, _handle_sigchld)
        log.info("Installed SIGCHLD handler (PID 1 mode)")
    else:
        log.info("Not PID 1 — SIGCHLD reaping via normal wait()")

    # Agent restart loop
    restarts = 0
    while restarts <= args.max_restarts:
        # Check goal exists
        if not Path(args.goal).exists():
            log.error("Goal file not found: %s", args.goal)
            if args.rescue:
                return rescue_shell(f"Goal not found: {args.goal}")
            return 2

        proc = spawn_agent(args.goal, args.state_dir)

        # Wait for agent
        try:
            ret = proc.wait()
        except KeyboardInterrupt:
            log.info("Interrupted — terminating agent")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return 130

        _children.pop(proc.pid, None)
        log.info("Agent exited with code %d (restart %d/%d)", ret, restarts, args.max_restarts)

        if ret == 0:
            log.info("Agent converged successfully — entering steady state")
            if args.exit_on_success:
                return 0
            # Re-run checks periodically (steady-state reconcile)
            log.info("Steady-state: re-checking every %ds (Ctrl-C to stop)", args.reconcile_interval)
            try:
                while True:
                    time.sleep(args.reconcile_interval)
                    # Re-check; if any fail, restart convergence
                    from agent.checks import all_passed, resolve_checks, run_checks
                    from agent.goal import goal_dir, load_goal

                    goal = load_goal(args.goal)
                    if not goal.accept:
                        log.info("No accept checks — steady state idle")
                        continue
                    resolved = resolve_checks(goal.accept, goal_dir(args.goal))
                    results = run_checks(resolved)
                    if not all_passed(results):
                        log.info("Checks now failing — re-entering convergence loop")
                        break
                    log.info("Steady-state checks still passing")
            except KeyboardInterrupt:
                return 0
            continue

        restarts += 1
        if restarts > args.max_restarts:
            log.error("Agent failed %d times — entering rescue", args.max_restarts)
            if args.rescue:
                return rescue_shell(f"Agent failed {args.max_restarts} times, last exit {ret}")
            return 1

        log.info("Restarting agent in %ds...", args.restart_delay)
        time.sleep(args.restart_delay)

    return 1


def rescue_shell(reason: str) -> int:
    log.error("RESCUE: %s", reason)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  inferkern rescue — {reason}", file=sys.stderr)
    print("  Goal: check /etc/inferkern/ and /var/lib/inferkern/journal.jsonl", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Try to exec a shell
    for shell in ["/bin/sh", "/bin/bash", "/bin/ash"]:
        if Path(shell).exists():
            log.info("Dropping to %s", shell)
            os.execv(shell, [shell])
    log.error("No shell found for rescue")
    return 1


def main():
    parser = argparse.ArgumentParser(description="inferkern-sup — PID 1 supervisor")
    parser.add_argument("--goal", default="/etc/inferkern/goal.yaml", help="Path to goal file")
    parser.add_argument("--goal-src", default=None, help="Host source for goal volume (QEMU 9p tag or device)")
    parser.add_argument("--state-dir", default="/var/lib/inferkern", help="Persistent state directory")
    parser.add_argument("--state-src", default=None, help="Host source for state volume")
    parser.add_argument("--max-restarts", type=int, default=3, help="Max agent restarts before rescue")
    parser.add_argument("--restart-delay", type=int, default=3, help="Seconds between restarts")
    parser.add_argument("--reconcile-interval", type=int, default=30, help="Steady-state re-check interval (s)")
    parser.add_argument("--no-boot-setup", action="store_true", help="Skip mounts/network (for Docker/testing)")
    parser.add_argument("--exit-on-success", action="store_true", help="Exit 0 when agent converges (for CI/harness)")
    parser.add_argument("--no-rescue", dest="rescue", action="store_false", default=True, help="Don't drop to rescue shell on failure")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    sys.exit(supervisor_main(args))


if __name__ == "__main__":
    main()
