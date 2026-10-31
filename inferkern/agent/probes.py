"""Discovery probes — gather facts about the machine for the agent context."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _run(cmd: str, timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"error: {e}"


def is_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/self/cgroup").read_text()
        if "docker" in cgroup or "kubepods" in cgroup:
            return True
    except Exception:
        pass
    return False


def is_qemu() -> bool:
    try:
        dmi = _run("cat /sys/class/dmi/id/product_name 2>/dev/tty 2>&1 || cat /sys/devices/virtual/dmi/id/product_name 2>&1")
        if "qemu" in dmi.lower() or "kvm" in dmi.lower() or "bochs" in dmi.lower():
            return True
    except Exception:
        pass
    return False


def collect_facts() -> dict:
    """Collect a snapshot of system facts."""
    facts: dict = {}
    facts["virt"] = {
        "docker": is_docker(),
        "qemu": is_qemu(),
    }
    facts["cpu"] = _run("nproc 2>&1; cat /proc/cpuinfo 2>&1 | head -20")
    facts["mem"] = _run("free -h 2>&1; cat /proc/meminfo 2>&1 | head -15")
    facts["disks"] = _run("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE 2>&1 || lsblk 2>&1 || echo no-lsblk")
    facts["net"] = _run("ip addr 2>&1 || ifconfig 2>&1; echo ---; ip route 2>&1 || route 2>&1; echo ---; cat /etc/resolv.conf 2>&1")
    facts["os"] = _run("cat /etc/os-release 2>&1; echo ---; uname -a 2>&1")
    facts["mounts"] = _run("mount 2>&1 | head -20; echo ---; df -h 2>&1 | head -20")
    facts["processes"] = _run("ps aux 2>&1 | head -20")
    facts["packages"] = _run("which apk 2>&1; apk info 2>&1 | head -30; echo ---; which apt-get 2>&1")
    # services / listening ports
    facts["ports"] = _run("ss -tlnp 2>&1 || netstat -tlnp 2>&1 || echo no-ss")
    return facts


def facts_summary(facts: dict) -> str:
    """Compact human-readable summary for LLM context."""
    lines = []
    for k, v in facts.items():
        snippet = v.strip()[:800] if isinstance(v, str) else str(v)[:800]
        lines.append(f"## {k}\n{snippet}\n")
    return "\n".join(lines)
