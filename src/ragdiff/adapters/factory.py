"""Factory for creating RAG tool adapters."""

import logging
from typing import Optional

from ..core.errors import AdapterRegistryError
from ..core.models import ToolConfig
from .abc import RagAdapter
from .registry import get_adapter, list_available_adapters

logger = logging.getLogger(__name__)

# Import adapters to ensure they're registered
# This triggers the auto-registration in each adapter module
from . import agentset, goodmem, vectara  # noqa: F401


def create_adapter(
    tool_name: str,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,
) -> RagAdapter:
    """Create a RAG tool adapter.

    Args:
        tool_name: Name of the tool (display name from YAML key)
        config: Tool configuration
        credentials: Optional credential overrides (env var name -> value)
            Takes precedence over environment variables.

    Returns:
        Initialized adapter instance

    Raises:
        AdapterRegistryError: If adapter is not registered

    Example:
        # Using environment variables
        adapter = create_adapter("vectara", config)

        # Using explicit credentials (multi-tenant)
        adapter = create_adapter(
            "vectara",
            config,
            credentials={"VECTARA_API_KEY": tenant_key}
        )
    """
    # Use config.adapter field if available, otherwise default to tool_name
    # This enables variants like "agentset-rerank" and "agentset-no-rerank"
    # to both use the "agentset" adapter class
    adapter_name = config.adapter or tool_name

    adapter_class = get_adapter(adapter_name)
    if not adapter_class:
        available = ", ".join(list_available_adapters())
        raise AdapterRegistryError(
            f"Unknown adapter: {adapter_name}. Available adapters: {available}"
        )

    logger.info(f"Creating {adapter_name} adapter for tool '{tool_name}'")

    try:
        adapter = adapter_class(config, credentials=credentials)
        return adapter
    except Exception as e:
        logger.error(f"Failed to create adapter for {tool_name}: {e}")
        raise


def get_available_adapters() -> list[str]:
    """Get list of available adapter names.

    Returns:
        List of registered adapter names
    """
    return list_available_adapters()
