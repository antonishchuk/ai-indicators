from .base import Collector
from .componentprices import ComponentPrices
from .diskprices import DiskPrices
from .ecos import Ecos
from .edgar import Edgar
from .fred import Fred
from .gpuperhour import GpuPerHour
from .litellm import LiteLLM
from .llm_prices import LlmPrices
from .npm import Npm
from .openrouter import OpenRouter
from .openrouter_endpoints import OpenRouterEndpoints
from .openrouter_usage import OpenRouterUsage
from .ornn import Ornn
from .pypistats import PyPIStats
from .ramp import Ramp
from .runpod import RunPod
from .siliconanalysts import SiliconAnalysts
from .stanford_memory import StanfordMemory
from .tsmc import Tsmc
from .yahoo import Yahoo

REGISTRY: dict[str, type[Collector]] = {
    c.name: c
    for c in (
        OpenRouter,
        OpenRouterEndpoints,
        OpenRouterUsage,
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
        Ramp,
        Ecos,
        ComponentPrices,
        StanfordMemory,
        DiskPrices,
        SiliconAnalysts,
    )
}

__all__ = ["Collector", "REGISTRY"]
