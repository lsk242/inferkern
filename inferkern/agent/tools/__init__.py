"""Tool registry bridge."""
from __future__ import annotations

from .exec_tools import TOOLS as EXEC_TOOLS
from .file_tools import TOOLS as FILE_TOOLS
from .pkg_tools import TOOLS as PKG_TOOLS
from .service_tools import TOOLS as SVC_TOOLS
from .system_tools import TOOLS as SYS_TOOLS

__all__ = ["TOOL_SCHEMAS", "TOOL_HANDLERS"]

TOOL_SCHEMAS, TOOL_HANDLERS = {}, {}

for group in (EXEC_TOOLS, FILE_TOOLS, PKG_TOOLS, SVC_TOOLS, SYS_TOOLS):
    for name, (schema, handler) in group.items():
        # allow group to return (schema, handler) or (schema, handler) with handler being callable
        TOOL_SCHEMAS[name] = schema
        TOOL_HANDLERS[name] = handler


def tool_definitions() -> list[dict]:
    """Return list of OpenAI tool function definitions."""
    return list(TOOL_SCHEMAS.values())
