"""State: facts + append-only journal persisted to STATE_DIR."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class State:
    """Persisted agent state: facts cache + journal.

    Layout under state_dir:
      journal.jsonl  — one JSON object per line (append-only)
      facts.json     — latest facts snapshot
    """

    def __init__(self, state_dir: str | Path) -> None:
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.dir / "journal.jsonl"
        self.facts_path = self.dir / "facts.json"
        self.facts: dict[str, Any] = self._load_facts()

    # -- facts --

    def _load_facts(self) -> dict[str, Any]:
        if self.facts_path.exists():
            try:
                return json.loads(self.facts_path.read_text())
            except Exception:
                return {}
        return {}

    def update_facts(self, patch: dict[str, Any]) -> None:
        self.facts.update(patch)
        self._save_facts()

    def set_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value
        self._save_facts()

    def _save_facts(self) -> None:
        self.facts_path.write_text(json.dumps(self.facts, indent=2, sort_keys=True))

    # -- journal --

    def append(self, entry: dict[str, Any]) -> None:
        """Append one journal entry (adds ts if missing)."""
        if "ts" not in entry:
            entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **entry}
        with self.journal_path.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read(self, tail: int | None = None) -> list[dict[str, Any]]:
        """Read journal entries, optionally last N."""
        if not self.journal_path.exists():
            return []
        lines = self.journal_path.read_text().splitlines()
        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                entries.append({"raw": line})
        if tail is not None:
            return entries[-tail:]
        return entries

    def journal_text(self, tail: int = 30) -> str:
        """Compact text summary of recent journal for LLM context."""
        entries = self.read(tail=tail)
        if not entries:
            return "(empty journal)"
        lines: list[str] = []
        for e in entries:
            lines.append(json.dumps(e, ensure_ascii=False))
        return "\n".join(lines)
