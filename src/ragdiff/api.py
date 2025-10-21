"""Public API for RAGDiff library.

This module provides the main programmatic interface for RAGDiff.
All functions are also exported from the top-level ragdiff package.
"""

from pathlib import Path
from typing import Any, Optional

from .adapters.factory import create_adapter
from .adapters.registry import list_available_adapters
from .comparison.engine import ComparisonEngine
from .core.config import Config
from .core.models import ComparisonResult, RagResult
from .evaluation.evaluator import LLMEvaluator


def query(
    config_path: str | Path,
    query_text: str,
    tool: str,
    top_k: int = 5,
) -> list[RagResult]:
    """Run a single query against one RAG system.

    Args:
        config_path: Path to YAML configuration file
        query_text: The search query to execute
        tool: Name of the tool to query (must be configured in config)
        top_k: Number of results to return (default: 5)

    Returns:
        List of RagResult objects containing the search results

    Raises:
        ConfigurationError: If config is invalid or tool not found
        AdapterError: If the adapter fails to execute the query

    Example:
        >>> from ragdiff import query
        >>> results = query("config.yaml", "What is RAG?", tool="vectara", top_k=5)
        >>> for result in results:
        ...     print(f"{result.score:.3f}: {result.text[:100]}")
    """
    # Load and validate configuration
    config = Config(Path(config_path))
    config.validate()

    # Check tool exists
    if tool not in config.tools:
        from .core.errors import ConfigurationError

        raise ConfigurationError(
            f"Tool '{tool}' not found in configuration. "
            f"Available tools: {', '.join(config.tools.keys())}"
        )

    # Create adapter and run query
    adapter = create_adapter(tool, config.tools[tool])
    return adapter.search(query_text, top_k=top_k)


def run_batch(
    config_path: str | Path,
    queries: list[str],
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> list[ComparisonResult]:
    """Run multiple queries against multiple RAG systems.

    Args:
        config_path: Path to YAML configuration file
        queries: List of query strings to execute
        tools: List of tool names to use (default: all configured tools)
        top_k: Number of results per query (default: 5)
        parallel: Run searches in parallel (default: True)
        evaluate: Run LLM evaluation on results (default: False)

    Returns:
        List of ComparisonResult objects, one per query

    Raises:
        ConfigurationError: If config is invalid or tools not found
        AdapterError: If any adapter fails to execute queries

    Example:
        >>> from ragdiff import run_batch
        >>> queries = ["What is RAG?", "What is vector search?"]
        >>> results = run_batch("config.yaml", queries, tools=["vectara", "goodmem"])
        >>> for result in results:
        ...     print(f"Query: {result.query}")
        ...     print(f"Tools: {', '.join(result.tool_results.keys())}")
    """
    # Load and validate configuration
    config = Config(Path(config_path))
    config.validate()

    # Determine which tools to use
    if tools is None:
        tool_names = list(config.tools.keys())
    else:
        tool_names = tools

    # Validate tools exist
    for tool_name in tool_names:
        if tool_name not in config.tools:
            from .core.errors import ConfigurationError

            raise ConfigurationError(
                f"Tool '{tool_name}' not found in configuration. "
                f"Available tools: {', '.join(config.tools.keys())}"
            )

    # Create adapters
    adapters = {}
    for tool_name in tool_names:
        adapters[tool_name] = create_adapter(tool_name, config.tools[tool_name])

    # Create comparison engine
    engine = ComparisonEngine(adapters)

    # Run queries
    results = []
    for query_text in queries:
        result = engine.run_comparison(query_text, top_k=top_k, parallel=parallel)

        # Optionally run LLM evaluation
        if evaluate:
            llm_config = config.get_llm_config()
            if llm_config:
                import os

                evaluator = LLMEvaluator(
                    model=llm_config.get("model", "claude-sonnet-4-20250514"),
                    api_key=os.getenv(
                        llm_config.get("api_key_env", "ANTHROPIC_API_KEY")
                    ),
                )
                result.llm_evaluation = evaluator.evaluate(result)

        results.append(result)

    return results


def compare(
    config_path: str | Path,
    query_text: str,
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> ComparisonResult:
    """Compare multiple RAG systems on a single query.

    Args:
        config_path: Path to YAML configuration file
        query_text: The search query to execute
        tools: List of tool names to compare (default: all configured tools)
        top_k: Number of results per tool (default: 5)
        parallel: Run searches in parallel (default: True)
        evaluate: Run LLM evaluation on results (default: False)

    Returns:
        ComparisonResult containing results from all tools

    Raises:
        ConfigurationError: If config is invalid or tools not found
        AdapterError: If any adapter fails to execute the query

    Example:
        >>> from ragdiff import compare
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
    # Load and validate configuration
    config = Config(Path(config_path))
    config.validate()

    # Determine which tools to use
    if tools is None:
        tool_names = list(config.tools.keys())
    else:
        tool_names = tools

    # Validate tools exist
    for tool_name in tool_names:
        if tool_name not in config.tools:
            from .core.errors import ConfigurationError

            raise ConfigurationError(
                f"Tool '{tool_name}' not found in configuration. "
                f"Available tools: {', '.join(config.tools.keys())}"
            )

    # Create adapters
    adapters = {}
    for tool_name in tool_names:
        adapters[tool_name] = create_adapter(tool_name, config.tools[tool_name])

    # Create comparison engine
    engine = ComparisonEngine(adapters)

    # Run comparison
    result = engine.run_comparison(query_text, top_k=top_k, parallel=parallel)

    # Optionally run LLM evaluation
    if evaluate:
        llm_config = config.get_llm_config()
        if llm_config:
            import os

            evaluator = LLMEvaluator(
                model=llm_config.get("model", "claude-sonnet-4-20250514"),
                api_key=os.getenv(llm_config.get("api_key_env", "ANTHROPIC_API_KEY")),
            )
            result.llm_evaluation = evaluator.evaluate(result)

    return result


def evaluate_with_llm(
    result: ComparisonResult,
    model: str = "claude-sonnet-4-20250514",
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
        EvaluationError: If LLM evaluation fails

    Example:
        >>> from ragdiff import compare, evaluate_with_llm
        >>> result = compare("config.yaml", "What is RAG?")
        >>> result = evaluate_with_llm(result)
        >>> print(f"Winner: {result.llm_evaluation.winner}")
        >>> print(f"Analysis: {result.llm_evaluation.analysis}")
    """
    import os

    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        from .core.errors import ConfigurationError

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

        # Build metadata dict
        metadata = {
            "name": name,
            "api_version": adapter_class.ADAPTER_API_VERSION,
            "required_env_vars": [],
            "options_schema": {},
        }

        # Try to get instance methods (these require a config, so we'll create a dummy one)
        try:
            # Create minimal dummy config
            from .core.models import ToolConfig

            dummy_config = ToolConfig(name=name, api_key_env="DUMMY_KEY")

            # Try to instantiate (may fail, that's ok)
            try:
                instance = adapter_class(dummy_config)
                metadata["required_env_vars"] = instance.get_required_env_vars()
                metadata["options_schema"] = instance.get_options_schema()
            except Exception:
                # If instantiation fails, try calling as class methods
                if hasattr(adapter_class, "get_required_env_vars"):
                    try:
                        metadata["required_env_vars"] = (
                            adapter_class.get_required_env_vars(adapter_class)
                        )
                    except Exception:
                        pass
                if hasattr(adapter_class, "get_options_schema"):
                    try:
                        metadata["options_schema"] = adapter_class.get_options_schema(
                            adapter_class
                        )
                    except Exception:
                        pass

        except Exception:
            pass

        # Add description if available
        if hasattr(adapter_class, "__doc__") and adapter_class.__doc__:
            # Use first line of docstring
            metadata["description"] = adapter_class.__doc__.strip().split("\n")[0]

        adapters_info.append(metadata)

    return adapters_info


def load_config(config_path: str | Path) -> Config:
    """Load and validate a configuration file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated Config object

    Raises:
        ConfigurationError: If config file is invalid

    Example:
        >>> from ragdiff import load_config
        >>> config = load_config("config.yaml")
        >>> print(f"Configured tools: {', '.join(config.tools.keys())}")
    """
    config = Config(Path(config_path))
    config.validate()
    return config


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
