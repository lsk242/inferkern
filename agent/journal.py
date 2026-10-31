"""Append-only JSONL journal."""
from __future__ import annotations

import json
import time
from pathlib import Path


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, entry: dict) -> None:
        entry = dict(entry)
        entry.setdefault("ts", time.time())
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                out.append({"raw": line})
        return out

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for l in self.path.read_text().splitlines() if l.strip())
