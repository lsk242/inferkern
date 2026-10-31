"""OpenAI-compatible LLM caller with budgets + stub mode."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class LLMResult:
    text: str
    tokens_used: int = 0
    stub: bool = False
    error: str = ""


class LLMClient:
    def __init__(self, endpoint: str | None = None, api_key: str | None = None, model: str | None = None):
        self.endpoint = (endpoint or os.environ.get("LLM_ENDPOINT") or os.environ.get("OPENAI_API_BASE") or "").strip() or None
        self.api_key = (api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip() or None
        self.model = model or os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        self.total_tokens = 0
        self.total_calls = 0

    @property
    def is_stub(self) -> bool:
        return not self.api_key or not self.endpoint

    def chat(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.2) -> LLMResult:
        if self.is_stub:
            return LLMResult(text="", stub=True, error="no LLM_API_KEY/LLM_ENDPOINT — stub mode")
        try:
            import requests  # type: ignore
        except ImportError:
            return LLMResult(text="", stub=True, error="requests not installed — stub mode")
        url = self.endpoint.rstrip("/") + "/chat/completions"
        # handle base URLs that already include /v1
        if url.endswith("/chat/completions/chat/completions"):
            url = url.replace("/chat/completions/chat/completions", "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            if resp.status_code != 200:
                return LLMResult(text="", error=f"LLM {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            text = ""
            try:
                text = data["choices"][0]["message"]["content"] or ""
            except Exception:
                text = json.dumps(data)[:2000]
            usage = data.get("usage", {})
            tokens = int(usage.get("total_tokens") or usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0) or 0)
            self.total_tokens += tokens
            self.total_calls += 1
            return LLMResult(text=text, tokens_used=tokens)
        except Exception as e:
            return LLMResult(text="", error=str(e)[:500])


def build_prompt(goal, facts: str, history: str) -> list[dict]:
    sys = (
        "You are inferkern, an autonomous Linux sysadmin agent. "
        "You must converge the system to the declared goal using the allowed tools. "
        "Respond with a JSON object: {\"thought\": \"...\", \"actions\": [{\"tool\": \"...\", \"args\": {...}}]}. "
        "Tools: exec(cmd), read(path), write(path,content), apk(package), probe(kind), service(name,action), check(), journal(n). "
        "Be idempotent. Prefer minimal steps."
    )
    user = f"Goal:\n{goal.raw}\n\nFacts:\n{facts}\n\nRecent journal:\n{history}\n\nWhat next?"
    return [{"role": "system", "content": sys}, {"role": "user", "content": user}]
