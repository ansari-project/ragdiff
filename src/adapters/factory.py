"""Factory for creating RAG tool adapters."""

from typing import Dict, Type, List
import logging

from .base import BaseRagTool
from .mawsuah import MawsuahAdapter
from .goodmem import GoodmemAdapter
from ..core.models import ToolConfig

logger = logging.getLogger(__name__)

# Registry of available adapters
ADAPTER_REGISTRY: Dict[str, Type[BaseRagTool]] = {
    "mawsuah": MawsuahAdapter,
    "goodmem": GoodmemAdapter,
}


def create_adapter(tool_name: str, config: ToolConfig) -> BaseRagTool:
    """Create a RAG tool adapter.

    Args:
        tool_name: Name of the tool
        config: Tool configuration

    Returns:
        Initialized adapter instance

    Raises:
        ValueError: If tool_name is not registered
    """
    if tool_name not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown tool: {tool_name}. Available tools: {available}"
        )

    adapter_class = ADAPTER_REGISTRY[tool_name]
    logger.info(f"Creating adapter for {tool_name}")

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