"""Raw-HTTP adapter for the Groq chat completions API (OpenAI-compatible)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from .base import (
    AdapterAuthError,
    AdapterError,
    AdapterRateLimitError,
    AdapterResponse,
    LLMAdapter,
    TokenUsage,
    ToolCall,
    parse_retry_after,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 60.0


class GroqAdapter(LLMAdapter):
    """Adapter for Groq's OpenAI-compatible chat completions endpoint."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)

    async def call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> AdapterResponse:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise AdapterAuthError("GROQ_API_KEY is not set in the environment")

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        started = time.perf_counter()
        try:
            response = await self._client.post(GROQ_BASE_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Groq request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code == 401:
            raise AdapterAuthError("Groq rejected the API key (401 Unauthorized)")
        if response.status_code == 429:
            raise AdapterRateLimitError(
                f"Groq rate limit: {response.text}", retry_after_seconds=parse_retry_after(response.headers)
            )
        if response.status_code >= 400:
            raise AdapterError(f"Groq returned {response.status_code}: {response.text}")

        data = response.json()
        choice = data["choices"][0]["message"]
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {}
            tool_calls.append(ToolCall(name=tc["function"]["name"], arguments=args))

        usage_raw = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
        )

        return AdapterResponse(
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            raw=data,
            text=choice.get("content"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
