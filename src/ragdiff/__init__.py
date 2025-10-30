"""RAGDiff v2.0 - Domain-based RAG system comparison framework.

RAGDiff is a framework for comparing Retrieval-Augmented Generation (RAG) systems
using a domain-based architecture with LLM evaluation support.

Basic Usage:
    >>> from ragdiff import execute_run, compare_runs
    >>>
    >>> # Execute a query set against a provider
    >>> run = execute_run(
    ...     domain="legal",
    ...     provider="vectara-default",
    ...     query_set="basic-questions"
    ... )
    >>>
    >>> # Compare multiple runs using LLM evaluation
    >>> comparison = compare_runs(
    ...     domain="legal",
    ...     run_ids=[run1.id, run2.id]
    ... )

Public API:
    Execution:
        - execute_run: Execute a query set against a provider

    Comparison:
        - compare_runs: Compare multiple runs using LLM evaluation
        - evaluate_run: Evaluate runs against reference answers

    Models:
        - Run: Execution result
        - Comparison: Comparison result
        - RetrievedChunk: Single retrieval result
        - QueryResult: Result for a single query
        - Provider: Base provider class

    Errors:
        - ConfigError: Configuration errors
        - RunError: Execution errors

Version:
    2.0.0
"""

from .comparison.evaluator import compare_runs
from .comparison.reference_evaluator import evaluate_run
from .core.errors import ConfigError, RunError
from .core.models import (
    Comparison,
    Domain,
    ProviderConfig,
    QueryResult,
    QuerySet,
    RetrievedChunk,
    Run,
    RunStatus,
)
from .execution import execute_run
from .providers import Provider, create_provider, register_tool
from .version import __version__

__all__ = [
    # Version
    "__version__",
    # Execution
    "execute_run",
    # Comparison
    "compare_runs",
    "evaluate_run",
    # Models
    "Run",
    "Comparison",
    "RetrievedChunk",
    "QueryResult",
    "Domain",
    "ProviderConfig",
    "QuerySet",
    "RunStatus",
    # Providers
    "Provider",
    "create_provider",
    "register_tool",
    # Errors
    "ConfigError",
    "RunError",
]
