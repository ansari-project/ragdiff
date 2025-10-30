"""Provider factory for RAGDiff v2.0.

Creates Provider instances from ProviderConfig objects by looking up the tool
in the registry and instantiating it with the provided configuration.

Example:
    >>> config = ProviderConfig(
    ...     name="vectara-default",
    ...     tool="vectara",
    ...     config={"api_key": "...", "corpus_id": 123}
    ... )
    >>> provider = create_provider(config)
    >>> chunks = provider.search("What is Islamic law?")
"""

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import ProviderConfig
from .abc import Provider
from .registry import get_tool

logger = get_logger(__name__)


def create_provider(config: ProviderConfig) -> Provider:
    """Create a Provider instance from a ProviderConfig.

    This function:
    1. Looks up the tool class in TOOL_REGISTRY using config.tool
    2. Instantiates the tool with config.config dict
    3. Returns the initialized Provider

    Args:
        config: ProviderConfig with tool name and configuration

    Returns:
        Initialized Provider instance

    Raises:
        ConfigError: If tool not found in registry
        RunError: If provider initialization fails

    Example:
        >>> config = load_provider("tafsir", "vectara-default")
        >>> provider = create_provider(config)
        >>> chunks = provider.search("What is Islamic law?", top_k=5)
    """
    logger.debug(f"Creating provider: {config.name} (tool: {config.tool})")

    # Get tool class from registry
    try:
        tool_class = get_tool(config.tool)
    except ConfigError as e:
        raise ConfigError(f"Failed to create provider '{config.name}': {e}") from e

    # Instantiate tool with config
    try:
        provider = tool_class(config=config.config)
        logger.info(f"Created provider '{config.name}' using tool '{config.tool}'")
        return provider

    except ConfigError:
        # Re-raise ConfigError as-is (don't wrap)
        raise

    except Exception as e:
        # Wrap other errors in RunError
        raise RunError(
            f"Failed to initialize provider '{config.name}' (tool: {config.tool}): {e}"
        ) from e


def validate_provider_config(config: ProviderConfig) -> None:
    """Validate that a provider config can be used to create a provider.

    Checks:
    - Tool is registered in TOOL_REGISTRY
    - Required config fields are present (tool-specific)

    Args:
        config: ProviderConfig to validate

    Raises:
        ConfigError: If validation fails

    Example:
        >>> config = load_provider("tafsir", "vectara-default")
        >>> validate_provider_config(config)  # Raises if invalid
    """
    # Check tool is registered
    try:
        get_tool(config.tool)
    except ConfigError as e:
        raise ConfigError(f"Invalid provider config '{config.name}': {e}") from e

    # Tool-specific validation would go here
    # For now, we rely on Provider.__init__ to validate config
    logger.debug(f"Provider config '{config.name}' is valid")
