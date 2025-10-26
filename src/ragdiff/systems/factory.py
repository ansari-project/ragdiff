"""System factory for RAGDiff v2.0.

Creates System instances from SystemConfig objects by looking up the tool
in the registry and instantiating it with the provided configuration.

Example:
    >>> config = SystemConfig(
    ...     name="vectara-default",
    ...     tool="vectara",
    ...     config={"api_key": "...", "corpus_id": 123}
    ... )
    >>> system = create_system(config)
    >>> chunks = system.search("What is Islamic law?")
"""

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models_v2 import SystemConfig
from .abc import System
from .registry import get_tool

logger = get_logger(__name__)


def create_system(config: SystemConfig) -> System:
    """Create a System instance from a SystemConfig.

    This function:
    1. Looks up the tool class in TOOL_REGISTRY using config.tool
    2. Instantiates the tool with config.config dict
    3. Returns the initialized System

    Args:
        config: SystemConfig with tool name and configuration

    Returns:
        Initialized System instance

    Raises:
        ConfigError: If tool not found in registry
        RunError: If system initialization fails

    Example:
        >>> config = load_system("tafsir", "vectara-default")
        >>> system = create_system(config)
        >>> chunks = system.search("What is Islamic law?", top_k=5)
    """
    logger.debug(f"Creating system: {config.name} (tool: {config.tool})")

    # Get tool class from registry
    try:
        tool_class = get_tool(config.tool)
    except ConfigError as e:
        raise ConfigError(
            f"Failed to create system '{config.name}': {e}"
        ) from e

    # Instantiate tool with config
    try:
        system = tool_class(config=config.config)
        logger.info(f"Created system '{config.name}' using tool '{config.tool}'")
        return system

    except ConfigError:
        # Re-raise ConfigError as-is (don't wrap)
        raise

    except Exception as e:
        # Wrap other errors in RunError
        raise RunError(
            f"Failed to initialize system '{config.name}' (tool: {config.tool}): {e}"
        ) from e


def validate_system_config(config: SystemConfig) -> None:
    """Validate that a system config can be used to create a system.

    Checks:
    - Tool is registered in TOOL_REGISTRY
    - Required config fields are present (tool-specific)

    Args:
        config: SystemConfig to validate

    Raises:
        ConfigError: If validation fails

    Example:
        >>> config = load_system("tafsir", "vectara-default")
        >>> validate_system_config(config)  # Raises if invalid
    """
    # Check tool is registered
    try:
        get_tool(config.tool)
    except ConfigError as e:
        raise ConfigError(
            f"Invalid system config '{config.name}': {e}"
        ) from e

    # Tool-specific validation would go here
    # For now, we rely on System.__init__ to validate config
    logger.debug(f"System config '{config.name}' is valid")
