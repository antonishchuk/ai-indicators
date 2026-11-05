from .base import Collector
from .edgar import Edgar
from .fred import Fred
from .gpuperhour import GpuPerHour
from .litellm import LiteLLM
from .llm_prices import LlmPrices
from .npm import Npm
from .openrouter import OpenRouter
from .openrouter_endpoints import OpenRouterEndpoints
from .ornn import Ornn
from .pypistats import PyPIStats
from .runpod import RunPod
from .tsmc import Tsmc
from .yahoo import Yahoo

REGISTRY: dict[str, type[Collector]] = {
    c.name: c
    for c in (
        OpenRouter,
        OpenRouterEndpoints,
        LiteLLM,
        LlmPrices,
        Ornn,
        RunPod,
        GpuPerHour,
        Yahoo,
        Edgar,
        Fred,
        PyPIStats,
        Npm,
        Tsmc,
    )
}

__all__ = ["Collector", "REGISTRY"]
