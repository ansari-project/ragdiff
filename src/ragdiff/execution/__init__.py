"""RAGDiff v2.0 Run Execution.

This module provides the execution engine for running query sets against systems.

Public API:
    - execute_run: Execute a query set against a system

Example:
    >>> from ragdiff.execution import execute_run
    >>>
    >>> run = execute_run(
    ...     domain="tafsir",
    ...     system="vectara-default",
    ...     query_set="test-queries",
    ...     concurrency=10
    ... )
    >>> print(f"Status: {run.status}, Results: {len(run.results)}")
"""

from .executor import execute_run

__all__ = ["execute_run"]
