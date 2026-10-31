#!/usr/bin/env python3
"""
inferkern supervisor — deterministic PID 1.

Owns: mounts (/proc,/sys,/dev), DHCP, zombie reaping, agent spawn with
restart budget, rescue shell fallback. No LLM calls here.

Config via environment + /etc/inferkern/* (goal volume) or kernel cmdline.
"""
from __future__ import annotations

import os
import sys
import time
import signal
import logging
import subprocess
import pathlib
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG = logging.getLogger("inferkern-sup")

def setup_logging() -> None:
    fmt = "%(asctime)s [sup] %(levelname)s: %(message)s"
    # Try to log to kmsg if available (visible via dmesg / console)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        if os.path.exists("/dev/kmsg"):
            fh = open("/dev/kmsg", "w")
            handlers.append(logging.StreamHandler(fh))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    """Supervisor config from env vars (overridable via goal volume later)."""
    def __init__(self) -> None:
        self.agent_cmd: list[str] = self._parse_agent_cmd()
        self.max_restarts: int = int(os.environ.get("INFERKERN_MAX_RESTARTS", "3"))
        self.restart_window_s: int = int(os.environ.get("INFERKERN_RESTART_WINDOW_S", "300"))
        self.rescue_shell: str = os.environ.get("INFERKERN_RESCUE_SHELL", "/bin/sh")
        self.goal_dir: str = os.environ.get("INFERKERN_GOAL_DIR", "/etc/inferkern")
        self.state_dir: str = os.environ.get("INFERKERN_STATE_DIR", "/var/lib/inferkern")
        # Kernel cmdline overrides
        self._apply_cmdline()

    def _parse_agent_cmd(self) -> list[str]:
        raw = os.environ.get("INFERKERN_AGENT_CMD", "python3 -m agent")
        # Simple split — agent cmd is not expected to have complex quoting
        return raw.split()

    def _apply_cmdline(self) -> None:
        try:
            with open("/proc/cmdline") as f:
                cmdline = f.read()
        except OSError:
            return
        for token in cmdline.split():
            if token.startswith("inferkern.max_restarts="):
                try:
                    self.max_restarts = int(token.split("=", 1)[1])
                except ValueError:
                    pass
            elif token.startswith("inferkern.agent_cmd="):
                self.agent_cmd = token.split("=", 1)[1].split(",")


# ---------------------------------------------------------------------------
# Mounts
# ---------------------------------------------------------------------------

def do_mount(source: str, target: str, fstype: str, flags: int = 0, data: str = "") -> None:
    """Call mount(2) via /bin/mount — keeps Python stdlib-only."""
    os.makedirs(target, exist_ok=True)
    cmd = ["mount", "-t", fstype]
    if data:
        cmd += ["-o", data]
    cmd += [source, target]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Already mounted is not an error
        if "already mounted" in result.stderr.lower() or "busy" in result.stderr.lower():
            LOG.info("mount %s already mounted", target)
        else:
            LOG.warning("mount %s failed: %s", target, result.stderr.strip())
    else:
        LOG.info("mounted %s -> %s (%s)", source, target, fstype)


def ensure_mounts() -> None:
    """Mount essential pseudo-filesystems for PID 1."""
    if os.getpid() != 1:
        LOG.info("not PID 1 (pid=%d), skipping mounts", os.getpid())
        return
    do_mount("proc", "/proc", "proc", data="nosuid,nodev,noexec")
    do_mount("sysfs", "/sys", "sysfs", data="nosuid,nodev,noexec")
    do_mount("devtmpfs", "/dev", "devtmpfs", data="nosuid,mode=0755")
    # devpts for pty allocation
    os.makedirs("/dev/pts", exist_ok=True)
    do_mount("devpts", "/dev/pts", "devpts", data="nosuid,noexec,gid=5,mode=620")
    # tmpfs for /run
    os.makedirs("/run", exist_ok=True)
    do_mount("tmpfs", "/run", "tmpfs", data="nosuid,nodev,mode=0755")
    LOG.info("essential mounts done")


# ---------------------------------------------------------------------------
# Network — DHCP
# ---------------------------------------------------------------------------

def bring_up_network() -> None:
    """Try DHCP via udhcpc (BusyBox) or dhclient/dhcpcd. Best-effort."""
    # Find interfaces
    ifaces: list[str] = []
    try:
        for name in os.listdir("/sys/class/net"):
            if name == "lo":
                continue
            ifaces.append(name)
    except OSError:
        pass

    if not ifaces:
        # Try to bring up lo at least
        subprocess.run(["ip", "link", "set", "lo", "up"], capture_output=True)
        LOG.info("no non-lo interfaces found, lo up only")
        return

    # Bring lo up first
    subprocess.run(["ip", "link", "set", "lo", "up"], capture_output=True)

    for iface in ifaces:
        subprocess.run(["ip", "link", "set", iface, "up"], capture_output=True)

    # Try DHCP clients in order of preference
    dhcp_cmds = [
        ["udhcpc", "-i", ifaces[0], "-q", "-t", "3"],
        ["udhcpc", "-i", ifaces[0]],
        ["dhclient", ifaces[0]],
        ["dhcpcd", ifaces[0]],
    ]
    for cmd in dhcp_cmds:
        binary = cmd[0]
        # Check existence
        found = False
        for p in os.environ.get("PATH", "/sbin:/usr/sbin:/bin:/usr/bin").split(":"):
            if os.path.exists(os.path.join(p, binary)):
                found = True
                break
        # Also check absolute
        if not found and not os.path.exists(f"/sbin/{binary}") and not os.path.exists(f"/usr/sbin/{binary}"):
            continue
        LOG.info("trying DHCP: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            LOG.info("DHCP succeeded on %s", ifaces[0])
            return
        else:
            LOG.warning("DHCP %s failed: %s", binary, result.stderr.strip()[:200])

    LOG.warning("all DHCP attempts failed or no client found; networking may be unavailable")


# ---------------------------------------------------------------------------
# Goal / state volumes (virtio or second disk)
# ---------------------------------------------------------------------------

def mount_volumes(cfg: Config) -> None:
    """Mount goal/state volumes if block devices exist for them.

    Convention:
      - /dev/vdb or /dev/sdb labelled INFERKERN_GOAL -> goal dir
      - /dev/vdb or label INFERKERN_STATE -> state dir (blank disk second partition eventually)
    Best-effort: missing devices are not fatal; blank disk setup is the agent's job.
    """
    # Try label-based mount first
    for label, mountpoint in [
        ("INFERKERN_GOAL", cfg.goal_dir),
        ("INFERKERN_STATE", cfg.state_dir),
    ]:
        dev = f"/dev/disk/by-label/{label}"
        if os.path.exists(dev):
            os.makedirs(mountpoint, exist_ok=True)
            result = subprocess.run(["mount", dev, mountpoint], capture_output=True, text=True)
            if result.returncode == 0:
                LOG.info("mounted label %s -> %s", label, mountpoint)
            else:
                LOG.warning("mount label %s failed: %s", label, result.stderr.strip())

    # Ensure state dir exists even without mount (rootfs fallback)
    os.makedirs(cfg.state_dir, exist_ok=True)
    os.makedirs(cfg.goal_dir, exist_ok=True)


# ---------------------------------------------------------------------------
# Signal handling + zombie reaping
# ---------------------------------------------------------------------------

_shutdown_requested = False
_child_exited = False

def _handle_sigterm(signum: int, frame: object) -> None:
    global _shutdown_requested
    LOG.info("received signal %d, shutting down", signum)
    _shutdown_requested = True

def _handle_sigchld(signum: int, frame: object) -> None:
    global _child_exited
    _child_exited = True

def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)
    signal.signal(signal.SIGCHLD, _handle_sigchld)
    # Ignore SIGPIPE
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)


def reap_zombies() -> list[tuple[int, int]]:
    """Reap all available zombie children. Returns list of (pid, exit_code)."""
    reaped: list[tuple[int, int]] = []
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if pid == 0:
            break
        if os.WIFEXITED(status):
            code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            code = -os.WTERMSIG(status)
        else:
            code = status
        reaped.append((pid, code))
    return reaped


# ---------------------------------------------------------------------------
# Agent lifecycle
# ---------------------------------------------------------------------------

def spawn_agent(cfg: Config) -> subprocess.Popen[bytes]:
    """Spawn the agent child process."""
    LOG.info("spawning agent: %s", " ".join(cfg.agent_cmd))
    env = os.environ.copy()
    # Ensure unbuffered output for journal tailing
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(cfg.agent_cmd, env=env)
    LOG.info("agent pid=%d", proc.pid)
    return proc


def rescue_shell(cfg: Config) -> None:
    """Drop to rescue shell. Never returns in normal VM boot (reboot to exit)."""
    LOG.warning("entering rescue shell (failures exhausted)")
    # Print banner to console
    banner = (
        "\n"
        "  *** inferkern rescue shell ***\n"
        "  Agent failed {n} times. Dropping to shell.\n"
        "  State dir: {state}\n"
        "  Goal dir:  {goal}\n"
        "  Type 'reboot -f' or 'poweroff -f' to exit.\n"
        "\n"
    ).format(n=cfg.max_restarts, state=cfg.state_dir, goal=cfg.goal_dir)
    try:
        sys.stderr.write(banner)
        sys.stderr.flush()
    except OSError:
        pass

    # Try shells in order
    for shell in [cfg.rescue_shell, "/bin/sh", "/bin/ash", "/bin/bash"]:
        if os.path.exists(shell):
            try:
                os.execv(shell, [shell])
            except OSError as e:
                LOG.warning("exec %s failed: %s", shell, e)
                continue
    LOG.error("no rescue shell available; sleeping forever")
    while True:
        time.sleep(3600)


def supervisor_main() -> None:
    setup_logging()
    cfg = Config()
    LOG.info("inferkern supervisor starting (pid=%d)", os.getpid())
    LOG.info("config: agent=%s max_restarts=%d window=%ds", cfg.agent_cmd, cfg.max_restarts, cfg.restart_window_s)

    if os.getpid() == 1:
        ensure_mounts()

    mount_volumes(cfg)
    bring_up_network()
    install_signal_handlers()

    # Restart budget tracking: timestamps of recent failures
    failures: list[float] = []
    agent_proc: Optional[subprocess.Popen[bytes]] = None

    # Initial spawn
    try:
        agent_proc = spawn_agent(cfg)
    except (OSError, FileNotFoundError) as e:
        LOG.error("failed to spawn agent: %s", e)
        # Fall through to rescue after budget check
        failures.append(time.monotonic())
        agent_proc = None

    global _shutdown_requested, _child_exited

    while not _shutdown_requested:
        # Wait a bit for SIGCHLD or shutdown
        # Use short poll to handle signals even if handler flag races
        for _ in range(20):
            if _shutdown_requested or _child_exited:
                break
            time.sleep(0.1)

        if _shutdown_requested:
            break

        # Reap and check if our agent died
        reaped = reap_zombies()
        agent_died = False
        agent_exit_code: Optional[int] = None
        for pid, code in reaped:
            LOG.info("reaped pid=%d exit=%d", pid, code)
            if agent_proc is not None and pid == agent_proc.pid:
                agent_died = True
                agent_exit_code = code

        # Also poll (covers case where waitpid already consumed it)
        if agent_proc is not None and not agent_died:
            ret = agent_proc.poll()
            if ret is not None:
                agent_died = True
                agent_exit_code = ret

        if agent_died:
            LOG.warning("agent exited with code %s", agent_exit_code)
            # Clean exit (0) means agent converged or was told to stop — don't restart
            if agent_exit_code == 0:
                LOG.info("agent exited cleanly; supervisor halting")
                break

            now = time.monotonic()
            # Prune failures outside window
            failures = [t for t in failures if now - t < cfg.restart_window_s]
            failures.append(now)

            if len(failures) > cfg.max_restarts:
                LOG.error("restart budget exhausted (%d failures in %ds)", len(failures), cfg.restart_window_s)
                rescue_shell(cfg)
                break  # only reached if rescue shell not available

            backoff = min(2 ** len(failures), 30)
            LOG.info("restarting agent in %ds (failure %d/%d)", backoff, len(failures), cfg.max_restarts)
            # Sleep with shutdown awareness
            for _ in range(backoff * 10):
                if _shutdown_requested:
                    break
                time.sleep(0.1)
            if _shutdown_requested:
                break
            _child_exited = False
            try:
                agent_proc = spawn_agent(cfg)
            except (OSError, FileNotFoundError) as e:
                LOG.error("spawn failed: %s", e)
                agent_proc = None
                continue
        else:
            _child_exited = False

    # Graceful shutdown
    if agent_proc is not None and agent_proc.poll() is None:
        LOG.info("terminating agent pid=%d", agent_proc.pid)
        try:
            agent_proc.terminate()
            try:
                agent_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                agent_proc.kill()
        except OSError:
            pass

    # Reap remaining
    reap_zombies()
    LOG.info("supervisor exiting")
    sys.exit(0)


if __name__ == "__main__":
    supervisor_main()
