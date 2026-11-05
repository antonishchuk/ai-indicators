"""Curated model baskets.

TIERS maps vendor -> tier -> ordered chain of LiteLLM keys, oldest to newest.
At any date the tier's price is the price of the newest chain member present
in the data on that date. Legacy keys that LiteLLM has since deleted are kept
on purpose: they exist in the historical snapshots used for back-fill.
"""
from __future__ import annotations

# OpenRouter model ids (open-weight) for the endpoints collector.
OPENROUTER_OPEN_WEIGHT = [
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-v4.1-flash",
    "moonshotai/kimi-k3.1-pro",
    "moonshotai/kimi-k3",
    "moonshotai/kimi-k2.6",
    "qwen/qwen3.8-flash",
    "qwen/qwen3.8-27b",
    "z-ai/glm-5.3",
    "z-ai/glm-5.3-flash",
    "minimax/minimax-m3",
    "minimax/minimax-m3.1-flash",
    "meta-llama/llama-4-maverick",
    "mistralai/mistral-large-4-0",
]

# OpenRouter author prefix -> provider_name values that are the model vendor itself.
OPENROUTER_FIRST_PARTY = {
    "deepseek": ("DeepSeek",),
    "moonshotai": ("Moonshot AI", "Moonshot"),
    "qwen": ("Alibaba", "Alibaba Cloud"),
    "z-ai": ("Z.ai", "Z.AI", "Zhipu"),
    "minimax": ("MiniMax",),
    "mistralai": ("Mistral",),
}

VENDOR_LABEL = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "xai": "xAI",
    "deepseek": "DeepSeek",
    "moonshot": "Kimi (Moonshot)",
    "qwen": "Qwen (Alibaba)",
    "minimax": "MiniMax",
    "mistral": "Mistral",
}

CLOSED = ["openai", "anthropic", "google", "xai"]
OPEN_WEIGHT = ["deepseek", "moonshot", "qwen", "minimax", "mistral"]

TIERS: dict[str, dict[str, list[str]]] = {
    "openai": {
        # most capable general model at the time
        "frontier": ["gpt-4", "gpt-4-turbo", "gpt-4o", "o1", "gpt-4.5-preview", "gpt-5", "gpt-5.5", "gpt-5.6", "gpt-6-astra"],
        # default workhorse (what "the API" means for most apps)
        "mid": ["gpt-3.5-turbo", "gpt-4o", "gpt-4.1", "gpt-5", "gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.6-sol", "gpt-6-sol", "gpt-6.1-sol"],
        # cheapest current model
        "small": ["gpt-4o-mini", "gpt-4.1-nano", "gpt-5-nano", "gpt-5.4-nano", "gpt-5.6-luna", "gpt-6-luna"],
    },
    "anthropic": {
        "frontier": [
            "claude-3-opus-20240229",
            "claude-opus-4-20250514",
            "claude-opus-4-1-20250805",
            "claude-opus-4-5",
            "claude-opus-5",
            "claude-fable-5",
            "claude-fable-5-1",
        ],
        "mid": [
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20240620",
            "claude-3-5-sonnet-20241022",
            "claude-3-7-sonnet-20250219",
            "claude-sonnet-4-20250514",
            "claude-sonnet-4-5",
            "claude-sonnet-4-6",
            "claude-sonnet-5",
            "claude-sonnet-5-5",
        ],
        "small": ["claude-3-haiku-20240307", "claude-3-5-haiku-20241022", "claude-haiku-4-5", "claude-haiku-5-5"],
    },
    "google": {
        "frontier": ["gemini/gemini-1.5-pro", "gemini/gemini-2.5-pro", "gemini/gemini-3.1-pro-preview", "gemini/gemini-4-argon"],
        "mid": [
            "gemini/gemini-1.5-flash",
            "gemini/gemini-2.0-flash",
            "gemini/gemini-2.5-flash",
            "gemini/gemini-3-flash-preview",
            "gemini/gemini-3.5-flash",
            "gemini/gemini-3.8-flash",
        ],
        "small": [
            "gemini/gemini-1.5-flash-8b",
            "gemini/gemini-2.0-flash-lite",
            "gemini/gemini-2.5-flash-lite",
            "gemini/gemini-3.1-flash-lite",
            "gemini/gemini-3.5-flash-lite",
        ],
    },
    "xai": {
        "frontier": ["xai/grok-beta", "xai/grok-2-1212", "xai/grok-3", "xai/grok-4", "xai/grok-4.20", "xai/grok-4.5", "xai/grok-4.7"],
    },
    "deepseek": {
        "frontier": ["deepseek-chat", "deepseek-v4-pro"],
        "small": ["deepseek-flash"],
    },
    "moonshot": {
        "frontier": [
            "moonshot/moonshot-v1-128k",
            "moonshot/kimi-k2-0711-preview",
            "moonshot/kimi-k2-thinking",
            "moonshot/kimi-k2.5",
            "moonshot/kimi-k3",
            "moonshot/kimi-k3.1-pro",
        ],
    },
    "qwen": {
        "frontier": ["dashscope/qwen-max", "dashscope/qwen3.7-max", "dashscope/qwen3.8-max"],
        "small": ["dashscope/qwen-turbo", "dashscope/qwen3.8-flash"],
    },
    "minimax": {
        "frontier": ["minimax/MiniMax-M1", "minimax/MiniMax-M2", "minimax/MiniMax-M2.5", "minimax/MiniMax-M3"],
    },
    "mistral": {
        "frontier": ["mistral/mistral-large-latest"],
        "mid": ["mistral/mistral-medium-latest"],
        "small": ["mistral/mistral-small-latest"],
    },
}
