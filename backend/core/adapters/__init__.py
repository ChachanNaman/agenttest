"""LLM adapter implementations and the model-name-based adapter factory."""

from .base import AdapterResponse, LLMAdapter, ToolCall, TokenUsage
from .groq import GroqAdapter
from .anthropic import AnthropicAdapter
from .openai import OpenAIAdapter
from .ollama import OllamaAdapter

GROQ_MODEL_MARKERS = ("llama", "mixtral", "gemma")
ANTHROPIC_MODEL_MARKERS = ("claude",)
OPENAI_MODEL_MARKERS = ("gpt",)

_ADAPTER_CACHE: dict[str, LLMAdapter] = {}


def get_adapter(model: str) -> LLMAdapter:
    """Select the correct LLM adapter for a given model name.

    Adapters are cached (one instance per adapter class) so their
    underlying httpx.AsyncClient connection pools are reused.
    """
    lowered = model.lower()
    if any(marker in lowered for marker in GROQ_MODEL_MARKERS):
        cls: type[LLMAdapter] = GroqAdapter
    elif any(marker in lowered for marker in ANTHROPIC_MODEL_MARKERS):
        cls = AnthropicAdapter
    elif any(marker in lowered for marker in OPENAI_MODEL_MARKERS):
        cls = OpenAIAdapter
    else:
        cls = OllamaAdapter

    if cls.__name__ not in _ADAPTER_CACHE:
        _ADAPTER_CACHE[cls.__name__] = cls()
    return _ADAPTER_CACHE[cls.__name__]


__all__ = [
    "AdapterResponse",
    "LLMAdapter",
    "ToolCall",
    "TokenUsage",
    "GroqAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
    "OllamaAdapter",
    "get_adapter",
]
