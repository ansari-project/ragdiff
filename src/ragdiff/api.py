"""Public API for RAGDiff library.

This module provides the main programmatic interface for RAGDiff.
All functions are also exported from the top-level ragdiff package.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from .adapters.factory import create_adapter
from .adapters.registry import list_available_adapters
from .comparison.engine import ComparisonEngine
from .core.config import Config
from .core.errors import ConfigurationError, ValidationError
from .core.models import ComparisonResult, RagResult, ToolConfig
from .evaluation.evaluator import LLMEvaluator

logger = logging.getLogger(__name__)

# Default LLM model for evaluations
DEFAULT_LLM_MODEL = "claude-sonnet-4-20250514"


def _validate_config_path(config_path: str | Path) -> Path:
    """Validate that config path exists and is readable.

    Args:
        config_path: Path to configuration file

    Returns:
        Resolved Path object

    Raises:
        ConfigurationError: If path doesn't exist or isn't readable
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    if not path.is_file():
        raise ConfigurationError(f"Configuration path is not a file: {path}")
    return path


def _validate_query_text(query_text: str) -> None:
    """Validate query text is non-empty.

    Args:
        query_text: Query string to validate

    Raises:
        ValidationError: If query text is empty or whitespace-only
    """
    if not query_text or not query_text.strip():
        raise ValidationError("query_text cannot be empty or whitespace-only")


def _validate_top_k(top_k: int) -> None:
    """Validate top_k parameter.

    Args:
        top_k: Number of results to return

    Raises:
        ValidationError: If top_k is not positive
    """
    if top_k < 1:
        raise ValidationError(f"top_k must be positive, got {top_k}")


def _validate_queries_list(queries: list[str]) -> None:
    """Validate queries list is non-empty.

    Args:
        queries: List of query strings

    Raises:
        ValidationError: If queries list is empty
    """
    if not queries:
        raise ValidationError("queries list cannot be empty")


def load_config(
    config: str | Path | dict,
    credentials: Optional[dict[str, str]] = None,
) -> Config:
    """Load and validate configuration.

    Supports multi-tenant usage by accepting credentials dict that takes
    precedence over environment variables.

    Args:
        config: Path to YAML file OR config dictionary
        credentials: Optional credential overrides (env var name -> value)
            Takes precedence over environment variables.

    Returns:
        Validated Config object

    Raises:
        ConfigurationError: If config is invalid

    Example:
        # From file with environment variables
        config = load_config("config.yaml")

        # From file with explicit credentials (multi-tenant)
        config = load_config("config.yaml", credentials={
            "VECTARA_API_KEY": "sk_abc123"
        })

        # From dict
        config_dict = {"tools": {"vectara": {...}}}
        config = load_config(config_dict, credentials={...})
    """
    if isinstance(config, dict):
        cfg = Config(config_dict=config, credentials=credentials)
    else:
        path = _validate_config_path(config)
        cfg = Config(config_path=path, credentials=credentials)

    cfg.validate()
    return cfg


def _load_and_validate_config(
    config_path: str | Path, tools: Optional[list[str]] = None
) -> tuple[Config, list[str]]:
    """Load config and validate tools exist.

    DEPRECATED: Use load_config() instead for new code.

    Args:
        config_path: Path to YAML configuration file
        tools: Optional list of tool names to validate (None = all tools)

    Returns:
        Tuple of (validated Config object, list of tool names to use)

    Raises:
        ConfigurationError: If config is invalid or tools not found
    """
    # Use load_config for consistency
    config = load_config(config_path)

    # Determine which tools to use
    if tools is None:
        tool_names = list(config.tools.keys())
    else:
        tool_names = tools

    # Validate tools exist
    for tool_name in tool_names:
        if tool_name not in config.tools:
            raise ConfigurationError(
                f"Tool '{tool_name}' not found in configuration. "
                f"Available tools: {', '.join(config.tools.keys())}"
            )

    return config, tool_names


def _create_llm_evaluator(config: Config, evaluate: bool) -> Optional[LLMEvaluator]:
    """Create LLM evaluator if evaluation is requested.

    Args:
        config: Config object containing LLM settings
        evaluate: Whether evaluation is requested

    Returns:
        LLMEvaluator instance or None if evaluation not requested/configured

    Raises:
        ConfigurationError: If evaluation requested but API key missing
    """
    if not evaluate:
        return None

    llm_config = config.get_llm_config()
    if not llm_config:
        logger.warning(
            "LLM evaluation requested but no LLM configuration found in config file. "
            "Add an 'llm' section with 'model' and 'api_key_env' to enable evaluation. "
            "Evaluation will be skipped."
        )
        return None

    # Get API key from config credential resolution
    api_key_env = llm_config.get("api_key_env", "ANTHROPIC_API_KEY")
    api_key = config._get_env_value(api_key_env)

    if not api_key:
        raise ConfigurationError(
            f"LLM evaluation requested but {api_key_env} environment variable not set. "
            f"Set the environment variable or disable evaluation."
        )

    model = llm_config.get("model", DEFAULT_LLM_MODEL)
    return LLMEvaluator(model=model, api_key=api_key)


def query(
    config: Config | str | Path,
    query_text: str,
    tool: str,
    top_k: int = 5,
) -> list[RagResult]:
    """Run a single query against one RAG system.

    Args:
        config: Config object OR path to YAML file (backward compatible)
        query_text: The search query to execute
        tool: Name of the tool to query (must be configured in config)
        top_k: Number of results to return (default: 5)

    Returns:
        List of RagResult objects containing the search results

    Raises:
        ConfigurationError: If config is invalid, file not found, or tool not found
        ValidationError: If query_text is empty or top_k is invalid
        AdapterError: If the adapter fails to execute the query

    Example:
        # New: Using Config object with credentials
        >>> from ragdiff import load_config, query
        >>> config = load_config("config.yaml", credentials={"VECTARA_API_KEY": "key"})
        >>> results = query(config, "What is RAG?", tool="vectara")

        # Old: Still works with file path (backward compatible)
        >>> results = query("config.yaml", "What is RAG?", tool="vectara", top_k=5)
        >>> for result in results:
        ...     print(f"{result.score:.3f}: {result.text[:100]}")
    """
    # Validate inputs
    _validate_query_text(query_text)
    _validate_top_k(top_k)

    # Handle both Config objects and paths (backward compat)
    if isinstance(config, Config):
        cfg = config
    else:
        cfg, _ = _load_and_validate_config(config, tools=[tool])

    # Validate tool exists
    if tool not in cfg.tools:
        raise ConfigurationError(
            f"Tool '{tool}' not found in configuration. "
            f"Available tools: {', '.join(cfg.tools.keys())}"
        )

    # Create adapter with credentials from Config and run query
    adapter = create_adapter(tool, cfg.tools[tool], credentials=cfg._credentials)
    return adapter.search(query_text, top_k=top_k)


def run_batch(
    config: Config | str | Path,
    queries: list[str],
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> list[ComparisonResult]:
    """Run multiple queries against multiple RAG systems.

    Args:
        config: Config object OR path to YAML file (backward compatible)
        queries: List of query strings to execute
        tools: List of tool names to use (default: all configured tools)
        top_k: Number of results per query (default: 5)
        parallel: Run searches in parallel (default: True)
        evaluate: Run LLM evaluation on results (default: False)

    Returns:
        List of ComparisonResult objects, one per query

    Raises:
        ConfigurationError: If config is invalid, file not found, or tools not found
        ValidationError: If queries list is empty or top_k is invalid
        AdapterError: If any adapter fails to execute queries

    Example:
        >>> from ragdiff import run_batch
        >>> queries = ["What is RAG?", "What is vector search?"]
        >>> results = run_batch("config.yaml", queries, tools=["vectara", "goodmem"])
        >>> for result in results:
        ...     print(f"Query: {result.query}")
        ...     print(f"Tools: {', '.join(result.tool_results.keys())}")
    """
    # Validate inputs
    _validate_queries_list(queries)
    _validate_top_k(top_k)

    # Handle both Config objects and paths (backward compat)
    if isinstance(config, Config):
        cfg = config
        # Determine which tools to use
        tool_names = tools if tools else list(cfg.tools.keys())
    else:
        cfg, tool_names = _load_and_validate_config(config, tools)

    # Create adapters with credentials from Config
    adapters = {}
    for tool_name in tool_names:
        adapters[tool_name] = create_adapter(
            tool_name, cfg.tools[tool_name], credentials=cfg._credentials
        )

    # Create comparison engine
    engine = ComparisonEngine(adapters)

    # Create LLM evaluator if needed
    evaluator = _create_llm_evaluator(cfg, evaluate)

    # Run queries
    results = []
    for query_text in queries:
        result = engine.run_comparison(query_text, top_k=top_k, parallel=parallel)

        # Optionally run LLM evaluation
        if evaluator:
            result.llm_evaluation = evaluator.evaluate(result)

        results.append(result)

    return results


def compare(
    config: Config | str | Path,
    query_text: str,
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> ComparisonResult:
    """Compare multiple RAG systems on a single query.

    Args:
        config: Config object OR path to YAML file (backward compatible)
        query_text: The search query to execute
        tools: List of tool names to compare (default: all configured tools)
        top_k: Number of results per tool (default: 5)
        parallel: Run searches in parallel (default: True)
        evaluate: Run LLM evaluation on results (default: False)

    Returns:
        ComparisonResult containing results from all tools

    Raises:
        ConfigurationError: If config is invalid, file not found, or tools not found
        ValidationError: If query_text is empty or top_k is invalid
        AdapterError: If any adapter fails to execute the query

    Example:
        # New: Using Config object with credentials
        >>> from ragdiff import load_config, compare
        >>> config = load_config("config.yaml", credentials={"VECTARA_API_KEY": "key"})
        >>> result = compare(config, "What is RAG?", tools=["vectara", "goodmem"])

        # Old: Still works with file path (backward compatible)
        >>> result = compare(
        ...     "config.yaml",
        ...     "What is RAG?",
        ...     tools=["vectara", "goodmem"],
        ...     evaluate=True
        ... )
        >>> print(f"Query: {result.query}")
        >>> for tool, results in result.tool_results.items():
        ...     print(f"{tool}: {len(results)} results")
        >>> if result.llm_evaluation:
        ...     print(f"Winner: {result.llm_evaluation.winner}")
    """
    # Validate inputs
    _validate_query_text(query_text)
    _validate_top_k(top_k)

    # Handle both Config objects and paths (backward compat)
    if isinstance(config, Config):
        cfg = config
        # Determine which tools to use
        tool_names = tools if tools else list(cfg.tools.keys())
    else:
        cfg, tool_names = _load_and_validate_config(config, tools)

    # Create adapters with credentials from Config
    adapters = {}
    for tool_name in tool_names:
        adapters[tool_name] = create_adapter(
            tool_name, cfg.tools[tool_name], credentials=cfg._credentials
        )

    # Create comparison engine
    engine = ComparisonEngine(adapters)

    # Run comparison
    result = engine.run_comparison(query_text, top_k=top_k, parallel=parallel)

    # Optionally run LLM evaluation
    evaluator = _create_llm_evaluator(cfg, evaluate)
    if evaluator:
        result.llm_evaluation = evaluator.evaluate(result)

    return result


def evaluate_with_llm(
    result: ComparisonResult,
    model: str = DEFAULT_LLM_MODEL,
    api_key: Optional[str] = None,
) -> ComparisonResult:
    """Evaluate comparison results using Claude LLM.

    Args:
        result: ComparisonResult to evaluate
        model: Claude model to use (default: claude-sonnet-4-20250514)
        api_key: Anthropic API key (default: from ANTHROPIC_API_KEY env var)

    Returns:
        The same ComparisonResult with llm_evaluation field populated

    Raises:
        ConfigurationError: If API key is not provided or found in environment
        EvaluationError: If LLM evaluation fails

    Example:
        >>> from ragdiff import compare, evaluate_with_llm
        >>> result = compare("config.yaml", "What is RAG?")
        >>> result = evaluate_with_llm(result)
        >>> print(f"Winner: {result.llm_evaluation.winner}")
        >>> print(f"Analysis: {result.llm_evaluation.analysis}")
    """
    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ConfigurationError(
            "ANTHROPIC_API_KEY environment variable not set and no api_key provided"
        )

    # Run evaluation
    evaluator = LLMEvaluator(model=model, api_key=api_key)
    result.llm_evaluation = evaluator.evaluate(result)

    return result


def get_available_adapters() -> list[dict[str, Any]]:
    """Get metadata for all available adapters.

    Returns:
        List of adapter metadata dictionaries, each containing:
        - name: Adapter name (e.g., "vectara")
        - api_version: Adapter API version
        - required_env_vars: List of required environment variables
        - options_schema: JSON Schema for adapter-specific options
        - description: Brief description (if available)

    Example:
        >>> from ragdiff import get_available_adapters
        >>> adapters = get_available_adapters()
        >>> for adapter in adapters:
        ...     print(f"{adapter['name']}: {adapter.get('description', 'No description')}")
        ...     print(f"  Required env vars: {adapter['required_env_vars']}")
    """
    from .adapters.registry import get_adapter

    adapter_names = list_available_adapters()
    adapters_info = []

    for name in adapter_names:
        # Get adapter class from registry
        adapter_class = get_adapter(name)
        if not adapter_class:
            continue

        # Build metadata dict with defaults
        metadata = {
            "name": name,
            "api_version": adapter_class.ADAPTER_API_VERSION,
            "required_env_vars": [],
            "options_schema": {},
        }

        # Try to get metadata from adapter instance
        try:
            # Create minimal dummy config for instantiation
            dummy_config = ToolConfig(name=name, api_key_env="DUMMY_KEY")
            instance = adapter_class(dummy_config)
            metadata["required_env_vars"] = instance.get_required_env_vars()
            metadata["options_schema"] = instance.get_options_schema()
        except (TypeError, AttributeError, KeyError) as e:
            # Instantiation failed, try class methods as fallback
            logger.debug(
                f"Could not instantiate adapter '{name}' for metadata: {e}. "
                f"Trying class methods."
            )
            if hasattr(adapter_class, "get_required_env_vars"):
                try:
                    metadata["required_env_vars"] = adapter_class.get_required_env_vars(
                        adapter_class
                    )
                except (TypeError, AttributeError) as e:
                    logger.debug(f"Could not get required_env_vars for '{name}': {e}")
            if hasattr(adapter_class, "get_options_schema"):
                try:
                    metadata["options_schema"] = adapter_class.get_options_schema(
                        adapter_class
                    )
                except (TypeError, AttributeError) as e:
                    logger.debug(f"Could not get options_schema for '{name}': {e}")
        except Exception as e:
            # Unexpected error - log but continue
            logger.warning(
                f"Unexpected error getting metadata for adapter '{name}': {e}"
            )

        # Add description if available
        if hasattr(adapter_class, "__doc__") and adapter_class.__doc__:
            # Use first line of docstring
            metadata["description"] = adapter_class.__doc__.strip().split("\n")[0]

        adapters_info.append(metadata)

    return adapters_info


def validate_config(config_path: str | Path) -> dict[str, Any]:
    """Validate a configuration file without loading it.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Dictionary with validation results:
        - valid: bool - Whether config is valid
        - errors: list[str] - List of validation errors (if any)
        - tools: list[str] - List of configured tool names
        - llm_configured: bool - Whether LLM evaluation is configured

    Example:
        >>> from ragdiff import validate_config
        >>> result = validate_config("config.yaml")
        >>> if result["valid"]:
        ...     print(f"Config is valid! Tools: {result['tools']}")
        ... else:
        ...     print(f"Errors: {result['errors']}")
    """
    try:
        config = Config(Path(config_path))
        config.validate()

        return {
            "valid": True,
            "errors": [],
            "tools": list(config.tools.keys()),
            "llm_configured": config.get_llm_config() is not None,
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "tools": [],
            "llm_configured": False,
        }
