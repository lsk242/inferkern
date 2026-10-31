"""File tools: read, write, list."""
from __future__ import annotations

from pathlib import Path


MAX_READ = 12000


def read_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"not found: {path}", "exists": False}
    try:
        if p.is_dir():
            entries = sorted([f.name for f in p.iterdir()])
            return {"path": path, "is_dir": True, "entries": entries[:500]}
        text = p.read_text(errors="replace")
        truncated = len(text) > MAX_READ
        return {
            "path": path,
            "exists": True,
            "is_dir": False,
            "content": text[:MAX_READ],
            "truncated": truncated,
            "size": len(text),
        }
    except Exception as e:
        return {"error": str(e), "path": path}


def write_file(path: str, content: str, mode: str = "0644") -> dict:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        try:
            p.chmod(int(mode, 8))
        except Exception:
            pass
        return {"ok": True, "path": path, "bytes": len(content)}
    except Exception as e:
        return {"ok": False, "error": str(e), "path": path}


def list_dir(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"error": f"not found: {path}"}
    if not p.is_dir():
        return {"error": f"not a directory: {path}"}
    try:
        entries = []
        for f in sorted(p.iterdir()):
            try:
                st = f.stat()
                entries.append({"name": f.name, "is_dir": f.is_dir(), "size": st.st_size})
            except Exception:
                entries.append({"name": f.name, "is_dir": None})
        return {"path": path, "entries": entries[:500]}
    except Exception as e:
        return {"error": str(e)}


TOOLS = {
    "read_file": (
        {
            "name": "read_file",
            "description": "Read a file or list a directory. Returns content (truncated at 12k) or directory entries.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File or directory path"}},
                "required": ["path"],
            },
        },
        lambda path, **_: read_file(path),
    ),
    "write_file": (
        {
            "name": "write_file",
            "description": "Write content to a file (creates parent dirs). Overwrites. Use for configs, html, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string", "description": "File content"},
                    "mode": {"type": "string", "description": "Octal file mode, e.g. 0644", "default": "0644"},
                },
                "required": ["path", "content"],
            },
        },
        lambda path, content, mode="0644", **_: write_file(path, content, mode=mode),
    ),
    "list_dir": (
        {
            "name": "list_dir",
            "description": "List a directory's entries with sizes.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
        lambda path, **_: list_dir(path),
    ),
}
