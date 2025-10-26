"""Tool registry for RAGDiff v2.0 providers.

The registry allows providers to register themselves for discovery and instantiation.
Tools register with a name (e.g., "vectara", "mongodb") and can be looked up
by that name when creating Provider instances from configuration.

Example:
    # Register a tool
    register_tool("vectara", VectaraProvider)

    # Get a tool class
    tool_class = get_tool("vectara")
    provider = tool_class(config={"api_key": "..."})

    # List all tools
    tools = list_tools()
    print(tools)  # ["vectara", "mongodb", "agentset"]
"""

from ..core.errors import ConfigError
from ..core.logging import get_logger
from .abc import Provider

logger = get_logger(__name__)

# Global registry: tool name -> Provider class
TOOL_REGISTRY: dict[str, type[Provider]] = {}


def register_tool(name: str, tool_class: type[Provider]) -> None:
    """Register a tool in the global registry.

    Args:
        name: Tool name (e.g., "vectara", "mongodb", "agentset")
        tool_class: System class to register

    Raises:
        ConfigError: If tool name already registered or invalid

    Example:
        >>> register_tool("vectara", VectaraProvider)
        >>> register_tool("mongodb", MongoDBProvider)
    """
    if not name:
        raise ConfigError("Tool name cannot be empty")

    if not name.replace("-", "").replace("_", "").isalnum():
        raise ConfigError(
            f"Tool name '{name}' must be alphanumeric with hyphens/underscores only"
        )

    if name in TOOL_REGISTRY:
        logger.warning(
            f"Tool '{name}' already registered. Overwriting with {tool_class.__name__}"
        )

    if not issubclass(tool_class, Provider):
        raise ConfigError(
            f"Tool class {tool_class.__name__} must inherit from Provider"
        )

    TOOL_REGISTRY[name] = tool_class
    logger.debug(f"Registered tool '{name}' -> {tool_class.__name__}")


def get_tool(name: str) -> type[Provider]:
    """Get a tool class from the registry.

    Args:
        name: Tool name (e.g., "vectara")

    Returns:
        System class

    Raises:
        ConfigError: If tool not found in registry

    Example:
        >>> tool_class = get_tool("vectara")
        >>> system = tool_class(config={"api_key": "..."})
    """
    if name not in TOOL_REGISTRY:
        available = ", ".join(sorted(TOOL_REGISTRY.keys()))
        raise ConfigError(
            f"Unknown tool '{name}'. Available tools: {available or '(none)'}"
        )

    return TOOL_REGISTRY[name]


def list_tools() -> list[str]:
    """List all registered tool names.

    Returns:
        Sorted list of tool names

    Example:
        >>> list_tools()
        ['agentset', 'mongodb', 'vectara']
    """
    return sorted(TOOL_REGISTRY.keys())


def is_tool_registered(name: str) -> bool:
    """Check if a tool is registered.

    Args:
        name: Tool name

    Returns:
        True if tool is registered, False otherwise

    Example:
        >>> is_tool_registered("vectara")
        True
        >>> is_tool_registered("unknown")
        False
    """
    return name in TOOL_REGISTRY
