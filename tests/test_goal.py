from agent.goal import parse_goal_text

def test_parse_basic():
    text = """
name: web-server
budget: { max_steps: 10, max_tokens: 1000, timeout_min: 5 }
accept: [checks/http-200.sh, checks/service-persists.sh]
constraints:
  allow: [exec, apk, write:/etc]
  deny: [mkfs:/dev/vda1]
"""
    g = parse_goal_text(text)
    assert g.name == "web-server"
    assert g.budget.max_steps == 10
    assert "checks/http-200.sh" in g.accept
    assert "exec" in g.allow
    assert "mkfs:/dev/vda1" in g.deny

def test_parse_web_server_goal():
    from pathlib import Path
    p = Path("goals/web-server/goal.md")
    if not p.exists():
        return
    from agent.goal import load_goal
    g = load_goal(p)
    assert g.name == "web-server"
    assert len(g.accept) >= 1
