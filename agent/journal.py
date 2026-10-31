"""Append-only journal — persistent state across restarts/reboots."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any


class Journal:
    """JSONL journal: one JSON object per line."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Touch file if missing
        if not self.path.exists():
            self.path.touch()

    def _now(self) -> str:
        return datetime.datetime.now(datetime.UTC).isoformat()

    def append(self, event: str, **fields: Any) -> dict:
        entry: dict[str, Any] = {"ts": self._now(), "event": event, **fields}
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return entry

    def read_all(self) -> list[dict]:
        entries: list[dict] = []
        if not self.path.exists():
            return entries
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def tail(self, n: int = 50) -> list[dict]:
        entries = self.read_all()
        return entries[-n:]

    def tail_text(self, n: int = 50) -> str:
        """Compact text summary of recent entries for LLM context."""
        lines: list[str] = []
        for e in self.tail(n):
            ts = e.get("ts", "")[:19]
            ev = e.get("event", "?")
            detail = {k: v for k, v in e.items() if k not in ("ts", "event")}
            detail_str = json.dumps(detail, default=str)[:500] if detail else ""
            lines.append(f"[{ts}] {ev}: {detail_str}")
        return "\n".join(lines)

    def entry_count(self) -> int:
        return len(self.read_all())


class State:
    """Simple JSON key-value state file (facts cache). Persists across restarts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text()) or {}
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def update(self, mapping: dict[str, Any]) -> None:
        self._data.update(mapping)
        self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, default=str) + "\n")
