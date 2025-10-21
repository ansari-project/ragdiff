"""RAG adapters package.

Importing this package automatically registers all built-in adapters.
"""

# Import adapters to trigger auto-registration
from . import agentset, goodmem, vectara  # noqa: F401

# Export registry functions for convenience
from .registry import (
    get_adapter,
    get_adapter_info,
    list_available_adapters,
    register_adapter,
)

__all__ = [
    "register_adapter",
    "get_adapter",
    "list_available_adapters",
    "get_adapter_info",
]
