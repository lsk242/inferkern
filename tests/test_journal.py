import tempfile
from pathlib import Path

from agent.journal import Journal, State


def test_journal_append_and_read():
    with tempfile.TemporaryDirectory() as d:
        j = Journal(Path(d) / "journal.jsonl")
        j.append("test_event", foo="bar")
        j.append("another", num=42)
        entries = j.read_all()
        assert len(entries) == 2
        assert entries[0]["event"] == "test_event"
        assert entries[0]["foo"] == "bar"
        assert entries[1]["num"] == 42


def test_journal_tail():
    with tempfile.TemporaryDirectory() as d:
        j = Journal(Path(d) / "journal.jsonl")
        for i in range(10):
            j.append(f"event_{i}")
        assert len(j.tail(3)) == 3
        assert j.tail(3)[-1]["event"] == "event_9"
        assert "event_9" in j.tail_text(3)


def test_state_persistence():
    with tempfile.TemporaryDirectory() as d:
        s = State(Path(d) / "state.json")
        s.set("key1", "val1")
        s.update({"key2": 42})
        assert s.get("key1") == "val1"
        assert s.get("key2") == 42

        # Reload
        s2 = State(Path(d) / "state.json")
        assert s2.get("key1") == "val1"


def test_journal_entry_count():
    with tempfile.TemporaryDirectory() as d:
        j = Journal(Path(d) / "j.jsonl")
        assert j.entry_count() == 0
        j.append("e1")
        assert j.entry_count() == 1
