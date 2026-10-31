"""Supervisor — deterministic pre-LLM setup + agent child supervision.

Runs as PID 1 in QEMU, or as Docker entrypoint wrapper. Handles:
  mounts (/proc /sys /dev if needed), basic DHCP, signal reaping,
  agent spawn with restart budget, rescue shell fallback, health logging.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# supervisor config from env
RESTART_LIMIT = int(os.environ.get("INFERKERN_RESTART_LIMIT", "3"))
RESTART_WINDOW_S = int(os.environ.get("INFERKERN_RESTART_WINDOW_S", "300"))
RESCUE_ON_FAIL = os.environ.get("INFERKERN_RESCUE", "shell")  # shell|halt|reboot


def log(msg: str) -> None:
    print(f"[inferkern-sup] {msg}", flush=True)


def try_mounts() -> None:
    """Mount essential pseudo-filesystems if not already mounted (QEMU bare boot)."""
    mounts = [
        ("proc", "/proc", "proc", "nosuid,noexec,nodev"),
        ("sysfs", "/sys", "sysfs", "nosuid,noexec,nodev"),
        ("devtmpfs", "/dev", "devtmpfs", "nosuid,mode=0755"),
        ("devpts", "/dev/pts", "devpts", "nosuid,noexec,gid=5,mode=0620"),
        ("tmpfs", "/run", "tmpfs", "nosuid,nodev,mode=0755"),
    ]
    for _src, tgt, fstype, opts in mounts:
        tgt_path = Path(tgt)
        try:
            if not tgt_path.exists():
                tgt_path.mkdir(parents=True, exist_ok=True)
            # check if already mounted
            with open("/proc/mounts") as f:
                if f" {tgt} " in f.read():
                    continue
            subprocess.run(["mount", "-t", fstype, "-o", opts, fstype, tgt], check=False, timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    # mdev / udev coldplug if available
    for cmd in ["mdev -s 2>/dev/null", "udevadm trigger 2>/dev/null; udevadm settle 2>/dev/null || true"]:
        try:
            subprocess.run(cmd, shell=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def try_network() -> None:
    """Bring up basic networking via DHCP (supervisor-owned L1-L3)."""
    # already have network?
    try:
        r = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and "default" in r.stdout:
            log("network: already has default route")
            return
    except Exception:
        pass

    candidates = [
        "udhcpc -i eth0 2>&1 | head -20",
        "udhcpc -i enp0s1 2>&1 | head -20",
        "dhclient -v 2>&1 | head -20",
        "dhcpcd --waitip 2>&1 | head -20",
        "ip link set eth0 up 2>&1; udhcpc -i eth0 2>&1 | head -20",
    ]
    # find first up interface
    try:
        r = subprocess.run(["ip", "-o", "link", "show"], capture_output=True, text=True, timeout=5)
        ifaces = []
        for line in (r.stdout or "").splitlines():
            if "LOOPBACK" in line or "DOWN" in line:
                continue
            # e.g. "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ..."
            parts = line.split(":")
            if len(parts) >= 2:
                ifaces.append(parts[1].strip())
        # try each iface with udhcpc/ip
        for iface in ifaces:
            if iface == "lo":
                continue
            log(f"network: trying {iface}")
            for prog in ("udhcpc", "dhclient", "dhcpcd"):
                if not shutil_which(prog):
                    continue
                cmd = {
                    "udhcpc": f"udhcpc -i {iface} -q 2>&1",
                    "dhclient": f"dhclient {iface} 2>&1",
                    "dhcpcd": f"dhcpcd {iface} 2>&1",
                }[prog]
                rr = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                out = (rr.stdout or "") + (rr.stderr or "")
                if rr.returncode == 0 or "lease" in out.lower():
                    log(f"network: {iface} via {prog} — {out.strip()[:200]}")
                    return
            # fallback: just bring link up
            subprocess.run(["ip", "link", "set", iface, "up"], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log(f"network: discovery failed: {e}")

    log("network: no DHCP success — continuing (agent will report if network needed)")


def shutil_which(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def try_goal_mount() -> None:
    """Mount goal volume if specified (QEMU: /dev/vdb etc.)."""
    goal_dev = os.environ.get("INFERKERN_GOAL_DEV", "")
    goal_mp = os.environ.get("INFERKERN_GOAL_MNT", "/etc/inferkern")
    if goal_dev and Path(goal_dev).exists():
        Path(goal_mp).mkdir(parents=True, exist_ok=True)
        subprocess.run(["mount", "-o", "ro", goal_dev, goal_mp], check=False, timeout=5)
        log(f"mounted goal volume {goal_dev} -> {goal_mp}")


def reap_children() -> None:
    """Reap any zombie children (PID 1 duty). Call periodically and on SIGCHLD."""
    try:
        while True:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
            log(f"reaped pid {pid} status {status}")
    except ChildProcessError:
        pass


def run_agent(goal_path: str, state_dir: str) -> int:
    """Spawn agent as child, return its exit code."""
    env = os.environ.copy()
    # ensure state dir exists
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    env.setdefault("INFERKERN_STATE_DIR", state_dir)
    env.setdefault("INFERKERN_GOAL", goal_path)

    # prefer installed module, fallback to python -m
    cmd = [sys.executable, "-m", "inferkern.agent.loop", goal_path]
    # if we are inside an installed venv/pip path, this works; otherwise try direct script
    log(f"spawning agent: {' '.join(cmd)}  goal={goal_path}")
    proc = subprocess.Popen(cmd, env=env)
    # reap loop while agent runs
    exit_code = None
    while exit_code is None:
        try:
            exit_code = proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            reap_children()
            # check if proc done via poll
            exit_code = proc.poll()
    # drain remaining zombies
    reap_children()
    return exit_code if exit_code is not None else 1


def rescue_shell() -> None:
    """Drop to rescue shell / halt."""
    if RESCUE_ON_FAIL == "halt":
        log("rescue: halting")
        subprocess.run(["poweroff", "-f"], check=False)
        return
    if RESCUE_ON_FAIL == "reboot":
        log("rescue: rebooting")
        subprocess.run(["reboot", "-f"], check=False)
        return
    # shell
    log("rescue: dropping to shell (exit shell to halt)")
    # also expose basic diagnostics
    for cmd in ["ip addr", "cat /proc/mounts", "cat /var/lib/inferkern/journal.jsonl 2>&1 | tail -50", "ls -la /etc/inferkern/ 2>&1"]:
        log(f"$ {cmd}")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            print((r.stdout or "") + (r.stderr or ""), flush=True)
        except Exception:
            pass
    for shell in ("/bin/sh", "/bin/bash", "/bin/ash"):
        if Path(shell).exists():
            try:
                # if stdin is a tty, interactive; else just log and halt
                if sys.stdin.isatty():
                    os.execv(shell, [shell])
                else:
                    subprocess.run([shell], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, timeout=3600)
                    break
            except Exception:
                continue
    log("rescue: no shell — halting")
    # last resort: keep pid 1 alive briefly for log collection, then poweroff if possible
    time.sleep(5)
    subprocess.run(["poweroff", "-f"], check=False)
    # if no poweroff, just sleep forever (don't exit PID 1)
    while True:
        time.sleep(3600)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="inferkern supervisor (PID 1 / entrypoint)")
    ap.add_argument("goal", nargs="?", default=os.environ.get("INFERKERN_GOAL", "goals/web-server/goal.yaml"), help="Goal file")
    ap.add_argument("--state-dir", default=os.environ.get("INFERKERN_STATE_DIR", ""), help="State dir")
    ap.add_argument("--no-mounts", action="store_true", help="Skip mount setup (Docker)")
    ap.add_argument("--no-network", action="store_true", help="Skip network setup")
    ap.add_argument("--oneshot", action="store_true", help="Run agent once, don't restart on failure (Docker default)")
    args, _unknown = ap.parse_known_args()

    # PID 1 niceties
    is_pid1 = os.getpid() == 1
    if is_pid1:
        # don't let Ctrl-C kill PID 1 accidentally; agent handles its own signals
        signal.signal(signal.SIGTERM, lambda *_: log("SIGTERM received — forwarding to agent child, then halting"))
        signal.signal(signal.SIGCHLD, lambda *_: reap_children())
        # prevent zombie accumulation generally
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass

    log(f"inferkern-sup starting (pid={os.getpid()} pid1={is_pid1}) goal={args.goal}")

    # Early setup (only if we look like a VM boot; Docker already has mounts/network)
    container = Path("/.dockerenv").exists()
    try:
        cgroup = Path("/proc/self/cgroup").read_text()
        if "docker" in cgroup or "kubepods" in cgroup:
            container = True
    except Exception:
        pass

    if not args.no_mounts and not container:
        log("setting up mounts")
        try_mounts()
        try_goal_mount()
    if not args.no_network and not container:
        log("setting up network")
        try_network()

    state_dir = args.state_dir or os.environ.get("INFERKERN_STATE_DIR", "") or ("/var/lib/inferkern" if not container else "state")
    goal_path = args.goal

    if not Path(goal_path).exists():
        # try alternate locations
        for alt in [f"/goals/{Path(goal_path).name}", f"/etc/inferkern/{Path(goal_path).name}", f"goals/web-server/goal.yaml"]:
            if Path(alt).exists():
                goal_path = alt
                break
        if not Path(goal_path).exists():
            log(f"goal not found: {goal_path} (tried alternates) — entering rescue")
            log("hint: mount goals to /goals or set INFERKERN_GOAL")
            rescue_shell()
            return

    # oneshot is default in container; restart loop for VM
    oneshot = args.oneshot or container or os.environ.get("INFERKERN_ONESHOT", "") in ("1", "true")

    failures: list[float] = []
    while True:
        code = run_agent(goal_path, state_dir)
        log(f"agent exited with code {code}")

        if code == 0:
            log("agent converged — success")
            # steady-state: in VM, sleep and re-verify periodically; in Docker, exit cleanly
            if oneshot:
                log("oneshot mode — supervisor exiting 0")
                sys.exit(0)
            log("steady-state: sleeping 60s then re-checking")
            time.sleep(60)
            # re-verify
            try:
                from inferkern.agent.goal import load_goal
                from inferkern.agent.checks import run_checks, all_passed

                goal = load_goal(goal_path)
                results = run_checks(goal)
                if all_passed(results):
                    log("steady-state checks still pass — sleeping again")
                    continue
                else:
                    log("steady-state checks failed — re-spawning agent")
                    continue
            except Exception:
                continue

        # failure path
        now = time.time()
        failures.append(now)
        # prune outside window
        failures = [t for t in failures if now - t < RESTART_WINDOW_S]
        if len(failures) > RESTART_LIMIT:
            log(f"agent failed {len(failures)} times in {RESTART_WINDOW_S}s (limit {RESTART_LIMIT}) — rescue")
            rescue_shell()
            return
        if oneshot:
            log(f"agent failed (code {code}) in oneshot mode — exiting 1")
            sys.exit(code if code != 0 else 1)
        backoff = min(2 ** len(failures), 30)
        log(f"restarting agent in {backoff}s ({len(failures)}/{RESTART_LIMIT} failures in window)")
        time.sleep(backoff)


if __name__ == "__main__":
    main()
