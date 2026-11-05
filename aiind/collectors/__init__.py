from .base import Collector
from .litellm import LiteLLM
from .llm_prices import LlmPrices
from .openrouter import OpenRouter
from .ornn import Ornn
from .runpod import RunPod

REGISTRY: dict[str, type[Collector]] = {
    c.name: c for c in (OpenRouter, LiteLLM, LlmPrices, Ornn, RunPod)
}

__all__ = ["Collector", "REGISTRY"]
