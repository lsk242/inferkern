"""Tool handler smoke tests."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inferkern.agent.tools import TOOL_SCHEMAS, TOOL_HANDLERS


def test_registry_has_expected_tools():
    for name in ["exec", "read_file", "write_file", "list_dir", "pkg_install", "pkg_update", "service_start", "service_status", "probe", "run_checks", "journal"]:
        assert name in TOOL_HANDLERS, f"missing tool {name}"
        assert name in TOOL_SCHEMAS


def test_tool_schemas_have_required_fields():
    for name, schema in TOOL_SCHEMAS.items():
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema


def test_exec_tool_runs():
    fn = TOOL_HANDLERS["exec"]
    r = fn(command="echo hello")
    assert r["exit_code"] == 0
    assert "hello" in r["output"]


def test_file_tools_roundtrip(tmp_path):
    write = TOOL_HANDLERS["write_file"]
    read = TOOL_HANDLERS["read_file"]
    p = str(tmp_path / "subdir" / "test.txt")
    r = write(path=p, content="hello inferkern")
    assert r["ok"] is True
    r2 = read(path=p)
    assert "hello inferkern" in r2["content"]
