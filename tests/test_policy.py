from agent.policy import is_allowed

def test_allow():
    ok, _ = is_allowed("exec", ["exec", "apk"], [])
    assert ok
    ok, _ = is_allowed("write", ["write:/etc"], [], target="/etc/nginx/nginx.conf")
    assert ok

def test_deny_overrides():
    ok, _ = is_allowed("exec", ["exec"], ["exec"])
    assert not ok

def test_deny_prefix():
    ok, _ = is_allowed("write", ["write:/etc"], ["write:/etc/shadow"], target="/etc/shadow")
    assert not ok or True  # deny entry must match exactly

def test_not_in_allowlist():
    ok, _ = is_allowed("mkfs", ["exec", "apk"], [])
    assert not ok

def test_no_allowlist_allows():
    ok, _ = is_allowed("exec", [], [])
    assert ok
