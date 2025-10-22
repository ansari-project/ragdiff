"""RAGDiff - Compare and evaluate RAG systems.

RAGDiff is a library and CLI tool for comparing Retrieval-Augmented Generation (RAG)
systems. It provides adapters for multiple RAG platforms and tools for evaluating
and comparing their performance.

Basic Usage:
    >>> from ragdiff import query, compare
    >>>
    >>> # Run a single query against one tool
    >>> results = query("config.yaml", "What is RAG?", tool="vectara")
    >>>
    >>> # Compare multiple tools on the same query
    >>> comparison = compare("config.yaml", "What is RAG?", tools=["vectara", "goodmem"])
    >>> print(f"Winner: {comparison.llm_evaluation.winner}")

Public API:
    Core Functions:
        - query: Run a single query against one RAG system
        - run_batch: Run multiple queries against multiple systems
        - compare: Compare multiple systems on a single query
        - evaluate_with_llm: Evaluate results using Claude LLM

    Configuration:
        - load_config: Load and validate a configuration file
        - validate_config: Validate a configuration file
        - get_available_adapters: Get metadata for all available adapters

    Models:
        - RagResult: Single search result
        - ComparisonResult: Comparison of multiple tools
        - LLMEvaluation: LLM evaluation results
        - Config: Configuration object

    Errors:
        - RagDiffError: Base exception class
        - ConfigurationError: Configuration errors
        - AdapterError: Adapter execution errors
        - AdapterRegistryError: Adapter registry errors
        - ValidationError: Data validation errors
        - EvaluationError: LLM evaluation errors

Version:
    1.0.0
"""

from .api import (
    compare,
    evaluate_with_llm,
    get_available_adapters,
    load_config,  # Already exported
    query,
    run_batch,
    validate_config,
)
from .core.config import Config
from .core.errors import (
    AdapterError,
    AdapterRegistryError,
    ConfigurationError,
    EvaluationError,
    RagDiffError,
    ValidationError,
)
from .core.models import ComparisonResult, LLMEvaluation, RagResult
from .version import ADAPTER_API_VERSION, __version__

__all__ = [
    # Version
    "__version__",
    "ADAPTER_API_VERSION",
    # Core API functions
    "query",
    "run_batch",
    "compare",
    "evaluate_with_llm",
    # Configuration
    "load_config",
    "validate_config",
    "get_available_adapters",
    "Config",
    # Models
    "RagResult",
    "ComparisonResult",
    "LLMEvaluation",
    # Errors
    "RagDiffError",
    "ConfigurationError",
    "AdapterError",
    "AdapterRegistryError",
    "ValidationError",
    "EvaluationError",
]
