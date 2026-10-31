"""LLM provider abstraction — OpenAI, Anthropic, mock.

All providers expose the same interface: given a prompt + tool schemas,
return the model's chosen tool calls (or a text response).
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """One tool invocation requested by the model."""

    tool: str
    args: dict[str, Any]
    call_id: str = ""


@dataclass
class LLMResponse:
    """Full response from the model."""

    content: str | None = None  # text reply if any
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)  # e.g. {"input_tokens": 100, "output_tokens": 50}
    raw: Any = None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send messages + optional tool schemas, get response."""

    @property
    @abstractmethod
    def name(self) -> str: ...


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (works for OpenAI, llama-server, etc.)
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    """Uses the OpenAI Chat Completions API (also compatible with llama-server)."""

    def __init__(self, endpoint: str, api_key: str, model: str = "gpt-4o-mini"):
        self.endpoint = endpoint.rstrip("/")
        if self.endpoint.endswith("/v1"):
            pass
        elif "/v1" not in self.endpoint:
            self.endpoint += "/v1"
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx required for OpenAIProvider — pip install httpx")

        # Convert our tool schemas to OpenAI format
        oai_tools = None
        if tools:
            oai_tools = [{"type": "function", "function": t} for t in tools]

        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if oai_tools:
            body["tools"] = oai_tools

        url = f"{self.endpoint}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        log.debug("LLM request to %s model=%s", url, self.model)
        resp = httpx.post(url, json=body, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc["function"]
            args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
            tool_calls.append(ToolCall(tool=fn["name"], args=args, call_id=tc.get("id", "")))

        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            raw=data,
        )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx required for AnthropicProvider")

        # Convert messages: Anthropic wants system as top-level, not in messages
        system_parts: list[str] = []
        anthro_msgs: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"] if isinstance(m["content"], str) else str(m["content"]))
            else:
                anthro_msgs.append(m)

        body: dict[str, Any] = {"model": self.model, "max_tokens": 4096, "messages": anthro_msgs}
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        if tools:
            body["tools"] = tools  # Anthropic tools already in correct shape for this path

        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

        resp = httpx.post("https://api.anthropic.com/v1/messages", json=body, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in data.get("content") or []:
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(tool=block["name"], args=block["input"], call_id=block["id"]))

        usage = data.get("usage", {})
        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
            raw=data,
        )


# ---------------------------------------------------------------------------
# Mock provider — rule-based convergence for testing without LLM cost
# ---------------------------------------------------------------------------


class MockProvider(LLMProvider):
    """Deterministic rule-based provider for tests and offline demos.

    ``plan`` is an ordered list of actions to emit. Each step the provider
    returns the next action(s), running ``check`` tools periodically.
    If no plan given, uses a default web-server convergence plan.
    """

    DEFAULT_PLAN: list[dict] = [
        {"tool": "exec", "args": {"command": "cat /etc/os-release"}},
        {"tool": "exec", "args": {"command": "apk update"}},
        {"tool": "exec", "args": {"command": "apk add nginx"}},
        {"tool": "write_file", "args": {"path": "/etc/nginx/http.d/inferkern.conf", "content": "server {\n    listen 80 default_server;\n    root /srv/www;\n    index index.html;\n    location / {\n        try_files $uri $uri/ =404;\n    }\n}\n"}},
        {"tool": "write_file", "args": {"path": "/srv/www/index.html", "content": "<!doctype html><html><body><h1>inferkern</h1><p>Converged by inferkern agent.</p></body></html>\n"}},
        {"tool": "exec", "args": {"command": "mkdir -p /run/nginx && nginx -t"}},
        {"tool": "exec", "args": {"command": "nginx"}},
        {"tool": "exec", "args": {"command": "sleep 1 && curl -sf http://127.0.0.1/ || wget -qO- http://127.0.0.1/ || echo 'check-fallback'"}},
    ]

    def __init__(self, plan: list[dict] | None = None):
        self.plan = plan if plan is not None else list(self.DEFAULT_PLAN)
        self._step = 0

    @property
    def name(self) -> str:
        return "mock"

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        if self._step < len(self.plan):
            item = self.plan[self._step]
            self._step += 1
            return LLMResponse(
                content=f"[mock step {self._step}/{len(self.plan)}] executing {item['tool']}",
                tool_calls=[ToolCall(tool=item["tool"], args=item["args"])],
                usage={"input_tokens": 100, "output_tokens": 50},
            )
        # Plan exhausted — report done
        return LLMResponse(content="[mock] plan complete — no more actions", tool_calls=[], usage={})

    def reset(self) -> None:
        self._step = 0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_provider(goal) -> LLMProvider:
    """Create the right provider from a Goal's LLM config."""
    llm = goal.llm
    provider = (llm.provider or "mock").lower()
    if provider == "mock":
        # Check if goal raw has a custom mock plan
        plan = goal.raw.get("mock_plan") if hasattr(goal, "raw") else None
        return MockProvider(plan=plan)
    if provider in ("openai", "openai-compatible", "llama", "llama-server"):
        if not llm.endpoint or not llm.api_key:
            raise ValueError("OpenAI-compatible provider needs endpoint + api_key in goal")
        return OpenAIProvider(endpoint=llm.endpoint, api_key=llm.api_key, model=llm.model)
    if provider == "anthropic":
        if not llm.api_key:
            raise ValueError("Anthropic provider needs api_key in goal")
        return AnthropicProvider(api_key=llm.api_key, model=llm.model)
    raise ValueError(f"Unknown LLM provider: {provider}")
