
from agent.budget import BudgetTracker
from agent.goal import Budget


def test_steps_exhausted():
    tracker = BudgetTracker(budget=Budget(max_steps=2, max_tokens=100000, timeout_min=60))
    assert tracker.exhausted() is None
    tracker.record_step()
    tracker.record_step()
    assert tracker.exhausted() is not None
    assert "step" in tracker.exhausted()


def test_tokens_exhausted():
    tracker = BudgetTracker(budget=Budget(max_steps=100, max_tokens=10, timeout_min=60))
    tracker.record_step(tokens=20)
    assert "token" in tracker.exhausted()


def test_wall_clock_exhausted():
    tracker = BudgetTracker(budget=Budget(max_steps=100, max_tokens=100000, timeout_min=0))
    # timeout 0 means immediately exhausted
    assert "wall-clock" in tracker.exhausted()


def test_summary():
    tracker = BudgetTracker(budget=Budget(max_steps=10, max_tokens=1000, timeout_min=5))
    tracker.record_step(tokens=100)
    assert "1/10" in tracker.summary()
