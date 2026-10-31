"""Budget enforcement — steps, tokens, wall-clock."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent.goal import Budget


@dataclass
class BudgetTracker:
    budget: Budget
    steps_used: int = 0
    tokens_used: int = 0  # approximate; sums reported usage
    _start_wall: float = field(default_factory=time.monotonic, repr=False)

    def record_step(self, tokens: int = 0) -> None:
        self.steps_used += 1
        self.tokens_used += tokens

    def exhausted(self) -> str | None:
        """Return reason string if any budget is exhausted, else None."""
        if self.steps_used >= self.budget.max_steps:
            return f"step budget exhausted ({self.steps_used}/{self.budget.max_steps})"
        if self.tokens_used >= self.budget.max_tokens:
            return f"token budget exhausted ({self.tokens_used}/{self.budget.max_tokens})"
        elapsed_min = (time.monotonic() - self._start_wall) / 60
        if elapsed_min >= self.budget.timeout_min:
            return f"wall-clock budget exhausted ({elapsed_min:.1f}/{self.budget.timeout_min} min)"
        return None

    def remaining_steps(self) -> int:
        return max(0, self.budget.max_steps - self.steps_used)

    def elapsed_minutes(self) -> float:
        return (time.monotonic() - self._start_wall) / 60

    def summary(self) -> str:
        return (
            f"steps {self.steps_used}/{self.budget.max_steps}, "
            f"tokens ~{self.tokens_used}/{self.budget.max_tokens}, "
            f"wall {self.elapsed_minutes():.1f}/{self.budget.timeout_min} min"
        )
