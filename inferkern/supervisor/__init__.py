"""inferkern supervisor package.

The implementation lives in :mod:`inferkern.supervisor.sup`; this module
only re-exports the entry point so ``python -m inferkern.supervisor.sup``
and ``from inferkern.supervisor import main`` both work.
"""
from __future__ import annotations

from .sup import main

__all__ = ["main"]
