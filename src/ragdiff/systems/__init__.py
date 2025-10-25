"""RAGDiff v2.0 Systems.

Systems are RAG tools (Vectara, MongoDB, Agentset, etc.) configured with
specific settings. All systems implement the System ABC with a search() method.

Public API:
    - System: Abstract base class
    - create_system: Factory function to create systems from config
    - register_tool: Register a tool in the registry
    - get_tool: Get a tool class from the registry
    - list_tools: List all registered tools

Example:
    >>> from ragdiff.systems import create_system
    >>> from ragdiff.core.loaders import load_system
    >>>
    >>> config = load_system("tafsir", "vectara-default")
    >>> system = create_system(config)
    >>> chunks = system.search("What is Islamic law?", top_k=5)
"""

from .abc import System
from .factory import create_system, validate_system_config
from .registry import get_tool, is_tool_registered, list_tools, register_tool

# Import system implementations to trigger registration
# These imports have side effects (register_tool calls)
from . import agentset, mongodb, vectara  # noqa: F401

__all__ = [
    # Core classes
    "System",
    # Factory
    "create_system",
    "validate_system_config",
    # Registry
    "register_tool",
    "get_tool",
    "list_tools",
    "is_tool_registered",
]
