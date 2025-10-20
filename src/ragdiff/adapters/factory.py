"""Factory for creating RAG tool adapters."""

import logging
from typing import Dict, List, Type

from ..core.models import ToolConfig
from .agentset import AgentsetAdapter
from .base import BaseRagTool
from .goodmem import GoodmemAdapter
from .vectara import VectaraAdapter

logger = logging.getLogger(__name__)

# Registry of available adapters
ADAPTER_REGISTRY: Dict[str, Type[BaseRagTool]] = {
    "vectara": VectaraAdapter,  # Vectara platform adapter
    "tafsir": VectaraAdapter,  # Vectara with Tafsir corpus
    "mawsuah": VectaraAdapter,  # Vectara with Mawsuah corpus
    "goodmem": GoodmemAdapter,
    "agentset": AgentsetAdapter,
}


def create_adapter(tool_name: str, config: ToolConfig) -> BaseRagTool:
    """Create a RAG tool adapter.

    Args:
        tool_name: Name of the tool (display name from YAML key)
        config: Tool configuration

    Returns:
        Initialized adapter instance

    Raises:
        ValueError: If adapter is not registered
    """
    # Use config.adapter field if available, otherwise default to tool_name
    # This enables variants like "agentset-rerank" and "agentset-no-rerank"
    # to both use the "agentset" adapter class
    adapter_name = config.adapter or tool_name

    if adapter_name not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available adapters: {available}"
        )

    adapter_class = ADAPTER_REGISTRY[adapter_name]
    logger.info(f"Creating {adapter_name} adapter for tool '{tool_name}'")

    try:
        adapter = adapter_class(config)
        return adapter
    except Exception as e:
        logger.error(f"Failed to create adapter for {tool_name}: {e}")
        raise


def register_adapter(name: str, adapter_class: Type[BaseRagTool]) -> None:
    """Register a new adapter type.

    Args:
        name: Name for the adapter
        adapter_class: Adapter class

    Raises:
        ValueError: If name already registered
    """
    if name in ADAPTER_REGISTRY:
        raise ValueError(f"Adapter '{name}' is already registered")

    if not issubclass(adapter_class, BaseRagTool):
        raise TypeError(
            f"Adapter must be a subclass of BaseRagTool, got {adapter_class}"
        )

    ADAPTER_REGISTRY[name] = adapter_class
    logger.info(f"Registered adapter: {name}")


def get_available_adapters() -> List[str]:
    """Get list of available adapter names.

    Returns:
        List of registered adapter names
    """
    return list(ADAPTER_REGISTRY.keys())
