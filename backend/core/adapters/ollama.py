"""Raw-HTTP adapter for a local Ollama server (OpenAI-compatible endpoint)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from .base import AdapterError, AdapterResponse, LLMAdapter, TokenUsage, ToolCall

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 120.0


class OllamaAdapter(LLMAdapter):
    """Adapter for a locally running Ollama instance. No API key required."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
        self._base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)

    async def call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> AdapterResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        started = time.perf_counter()
        try:
            response = await self._client.post(self._base_url, json=payload)
        except httpx.HTTPError as exc:
            raise AdapterError(
                f"Ollama request failed (is `ollama serve` running at {self._base_url}?): {exc}"
            ) from exc
        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code >= 400:
            raise AdapterError(f"Ollama returned {response.status_code}: {response.text}")

        data = response.json()
        choice = data["choices"][0]["message"]
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            raw_args = tc["function"]["arguments"]
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = raw_args
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
