"""RAGDiff v2.0 Providers.

Providers are RAG tools (Vectara, MongoDB, Agentset, OpenAPI, FAISS, Goodmem, etc.)
configured with specific settings. All providers implement the Provider ABC with a search() method.

Public API:
    - Provider: Abstract base class
    - create_provider: Factory function to create providers from config
    - register_tool: Register a tool in the registry
    - get_tool: Get a tool class from the registry
    - list_tools: List all registered tools

Example:
    >>> from ragdiff.providers import create_provider
    >>> from ragdiff.core.loaders import load_provider
    >>>
    >>> config = load_provider("tafsir", "vectara-default")
    >>> provider = create_provider(config)
    >>> chunks = provider.search("What is Islamic law?", top_k=5)
"""

# Import provider implementations to trigger registration

# These imports have side effects (register_tool calls)

from . import (
    agentset,
    bm25,
    faiss,
    goodmem,
    google_file_search,
    mongodb,
    openapi,
    vectara,
)  # noqa: F401
from .abc import Provider
from .factory import create_provider, validate_provider_config
from .registry import get_tool, is_tool_registered, list_tools, register_tool

__all__ = [
    # Core classes
    "Provider",
    # Factory
    "create_provider",
    "validate_provider_config",
    # Registry
    "register_tool",
    "get_tool",
    "list_tools",
    "is_tool_registered",
]
