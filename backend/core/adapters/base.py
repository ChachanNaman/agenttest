"""Abstract LLM adapter interface and shared response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class AdapterError(RuntimeError):
    """Raised when an LLM provider call fails after retries are exhausted."""


class AdapterAuthError(AdapterError):
    """Raised when the provider rejects the request due to a missing/invalid API key."""


class AdapterRateLimitError(AdapterError):
    """Raised on HTTP 429. Retrying immediately is pointless against a per-minute quota,
    so the runner backs this off on a much longer schedule than a generic AdapterError."""

    def __init__(self, message: str, retry_after_seconds: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass
class ToolCall:
    """A single tool/function invocation extracted from a model response."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    """Token accounting for a single model call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class AdapterResponse:
    """Normalized response returned by every LLMAdapter implementation."""

    tool_calls: list[ToolCall]
    usage: TokenUsage
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict)
    text: Optional[str] = None


def parse_retry_after(headers: Any) -> Optional[float]:
    """Extract a Retry-After hint (seconds) from a 429 response's headers, if present."""
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class LLMAdapter:
    """Abstract base class for a raw-HTTP LLM provider adapter."""

    async def call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> AdapterResponse:
        """Send a chat-completion request with tool definitions and return a normalized response.

        Args:
            system: The system prompt.
            messages: Prior conversation turns as {"role": ..., "content": ...} dicts.
            tools: Tool schemas in OpenAI function-calling format
                   (adapters translate to their own provider format as needed).
            model: The provider-specific model identifier.
        """
        raise NotImplementedError

    async def aclose(self) -> None:
        """Release any held resources (e.g. the underlying HTTP client)."""
        raise NotImplementedError
