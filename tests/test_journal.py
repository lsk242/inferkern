import tempfile, pathlib
from agent.journal import Journal

def test_append_and_tail(tmp_path=None):
    if tmp_path is None:
        import tempfile, os
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "j.jsonl"
    else:
        p = pathlib.Path(tmp_path) / "j.jsonl"
    j = Journal(p)
    j.append({"event": "a", "x": 1})
    j.append({"event": "b"})
    assert j.count() == 2
    tail = j.tail(1)
    assert tail[0]["event"] == "b"
