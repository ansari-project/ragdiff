"""Pricing utilities for RAGDiff."""

from typing import Optional

import litellm
import tiktoken

# Pricing constants (USD per 1M tokens)
# Updated: Nov 2025 (Estimated based on search results)

# Google Gemini
GEMINI_PRICING = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},  # < 128k context
    "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},  # < 128k context
    "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
    },  # Estimated/Placeholder for newer model
    "gemini-2.5-flash": {"input": 0.10, "output": 0.40},  # Estimated/Placeholder
    "gemini-2.5-flash-lite": {"input": 0.07, "output": 0.28},  # Estimated/Placeholder
    "gemini-2.5-pro": {"input": 2.50, "output": 7.50},  # Estimated/Placeholder
}

# OpenAI
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

# Anthropic
ANTHROPIC_PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}


def count_tokens(model: str, text: str) -> int:
    """Count tokens in a text using LiteLLM (or tiktoken for OpenAI fallback)."""
    try:
        # Use litellm.encode for broader model support
        return len(litellm.encode(model=model, text=text))
    except Exception:
        # Fallback to tiktoken for OpenAI models if litellm fails or not available
        if model.startswith("gpt") or model.startswith("text-davinci"):
            try:
                encoding = tiktoken.encoding_for_model(model)
                return len(encoding.encode(text))
            except KeyError:
                # Fallback to a common encoding if model not found in tiktoken
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
        # Basic word count fallback if no specific tokenizer
        return len(text.split())


def calculate_llm_cost(
    model: str, input_tokens: int, output_tokens: int
) -> Optional[float]:
    """Calculate cost for LLM usage.

    Args:
        model: Model name (e.g. "gemini-1.5-flash", "gpt-4o")
        input_tokens: Number of prompt tokens
        output_tokens: Number of completion/response tokens

    Returns:
        Estimated cost in USD, or None if model pricing is unknown.
    """
    # Normalize model string (handle prefixes like "models/")
    clean_model = model.lower().replace("models/", "")

    # Check providers
    pricing = None

    # Check Gemini
    for k, v in GEMINI_PRICING.items():
        if k in clean_model:  # Prefix match or exact match
            pricing = v
            break

    if not pricing:
        # Check OpenAI
        for k, v in OPENAI_PRICING.items():
            if k in clean_model:
                pricing = v
                break

    if not pricing:
        # Check Anthropic
        for k, v in ANTHROPIC_PRICING.items():
            if k in clean_model:
                pricing = v
                break

    if pricing:
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    return None
