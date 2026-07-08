"""Raw-HTTP adapter for the Anthropic Messages API."""

from __future__ import annotations

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

ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
REQUEST_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_TOKENS = 4096


def _to_anthropic_tool(openai_tool: dict[str, Any]) -> dict[str, Any]:
    """Translate an OpenAI-format tool schema into Anthropic's tool format."""
    fn = openai_tool["function"]
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic's native Messages API (not OpenAI-compatible)."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)

    async def call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> AdapterResponse:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise AdapterAuthError("ANTHROPIC_API_KEY is not set in the environment")

        payload: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": DEFAULT_MAX_TOKENS,
        }
        if tools:
            payload["tools"] = [_to_anthropic_tool(t) for t in tools]

        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        try:
            response = await self._client.post(ANTHROPIC_BASE_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Anthropic request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        if response.status_code == 401:
            raise AdapterAuthError("Anthropic rejected the API key (401 Unauthorized)")
        if response.status_code == 429:
            raise AdapterRateLimitError(
                f"Anthropic rate limit: {response.text}", retry_after_seconds=parse_retry_after(response.headers)
            )
        if response.status_code >= 400:
            raise AdapterError(f"Anthropic returned {response.status_code}: {response.text}")

        data = response.json()
        tool_calls = []
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                tool_calls.append(ToolCall(name=block["name"], arguments=block.get("input", {})))
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        usage_raw = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("input_tokens", 0),
            completion_tokens=usage_raw.get("output_tokens", 0),
        )

        return AdapterResponse(
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            raw=data,
            text="\n".join(text_parts) if text_parts else None,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
