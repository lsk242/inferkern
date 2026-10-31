"""LLM client — OpenAI-compatible chat completions with tool calling."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx


@dataclass
class LLMConfig:
    endpoint: str  # e.g. https://api.openai.com/v1 or http://localhost:8080/v1
    api_key: str
    model: str

    @classmethod
    def from_env_and_goal(cls, goal=None) -> "LLMConfig | None":
        """Resolve endpoint/key/model from env overrides, then goal, then defaults.

        Env vars: INFERKERN_LLM_ENDPOINT, INFERKERN_LLM_API_KEY, INFERKERN_LLM_MODEL
        If endpoint is missing -> dry-run / heuristic fallback (no LLM).
        """
        endpoint = os.environ.get("INFERKERN_LLM_ENDPOINT", "")
        api_key = os.environ.get("INFERKERN_LLM_API_KEY", "")
        model = os.environ.get("INFERKERN_LLM_MODEL", "")

        if goal is not None:
            if not endpoint and goal.llm_endpoint:
                endpoint = goal.llm_endpoint
            if not api_key and goal.llm_api_key:
                api_key = goal.llm_api_key
            if not model and goal.llm_model:
                model = goal.llm_model

        endpoint = endpoint.strip().rstrip("/")
        if not endpoint:
            return None
        if not model:
            model = "gpt-4o-mini"  # sensible default if model not specified
        return cls(endpoint=endpoint, api_key=api_key, model=model)


@dataclass
class LLMResponse:
    content: str  # assistant text
    tool_calls: list[dict]  # [{"id":..., "name":..., "arguments":{}}]
    usage: dict
    raw: dict


TOOL_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
TOOL_JSON_RE2 = re.compile(r"(\{[^{}]*\"tool\"\s*:[^{}]*\})", re.DOTALL)


def _extract_tool_calls_from_text(text: str) -> list[dict]:
    """Fallback: extract {\"tool\":..., \"args\":...} from free-form text."""
    calls: list[dict] = []
    # try JSON code fences first
    for m in TOOL_JSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
            calls.extend(_normalize_tool_obj(obj))
        except Exception:
            continue
    # also try raw JSON objects with "tool" key
    if not calls:
        for m in TOOL_JSON_RE2.finditer(text):
            try:
                obj = json.loads(m.group(1))
                calls.extend(_normalize_tool_obj(obj))
            except Exception:
                continue
    return calls


def _normalize_tool_obj(obj: dict | list) -> list[dict]:
    if isinstance(obj, list):
        out: list[dict] = []
        for item in obj:
            out.extend(_normalize_tool_obj(item))
        return out
    if not isinstance(obj, dict):
        return []
    # support {"tool": "exec", "args": {...}} or {"name": ...} or {"tool_calls": [...]}
    if "tool_calls" in obj:
        return _normalize_tool_obj(obj["tool_calls"])
    if "tools" in obj and isinstance(obj["tools"], list):
        return _normalize_tool_obj(obj["tools"])
    name = obj.get("tool") or obj.get("name") or obj.get("function")
    if not name:
        return []
    args = obj.get("args") or obj.get("arguments") or obj.get("parameters") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"_raw": args}
    return [{"id": f"fallback-{name}", "name": name, "arguments": args}]


class LLMClient:
    def __init__(self, config: LLMConfig, http_timeout: float = 60.0) -> None:
        self.config = config
        self.http_timeout = http_timeout

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Call /v1/chat/completions. Returns content + tool_calls."""
        # Normalize endpoint: if user passed full /chat/completions, don't double it
        endpoint = self.config.endpoint
        if endpoint.endswith("/chat/completions"):
            url = endpoint
        else:
            url = endpoint.rstrip("/") + "/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        body: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = tool_choice

        try:
            with httpx.Client(timeout=self.http_timeout) as client:
                resp = client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            # surface body for debugging
            detail = e.response.text[:1000] if e.response is not None else str(e)
            raise RuntimeError(f"LLM HTTP {e.response.status_code if e.response else '?'}: {detail}") from e
        except Exception as e:
            raise RuntimeError(f"LLM request failed: {e}") from e

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}

        content: str = msg.get("content") or ""
        raw_tool_calls = msg.get("tool_calls") or []
        tool_calls: list[dict] = []
        for tc in raw_tool_calls:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:
                args = {"_raw": args_raw}
            tool_calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": args})

        # fallback: parse tool calls from text if model didn't use tool_calls
        if not tool_calls and content:
            fallback = _extract_tool_calls_from_text(content)
            if fallback:
                tool_calls = fallback

        usage = data.get("usage") or {}

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage, raw=data)

    def dry_run_response(self, prompt_hint: str = "") -> LLMResponse:
        """Return a no-op response for dry-run / no-LLM mode."""
        return LLMResponse(
            content=f"[dry-run: no LLM configured] {prompt_hint}",
            tool_calls=[],
            usage={},
            raw={"dry_run": True},
        )
