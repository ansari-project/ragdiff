"""Parity testing framework for RAGDiff CLI and library.

This module provides utilities for testing that the CLI and library APIs
produce identical results when given the same inputs.
"""

from .framework import (
    ParityTest,
    ParityTestResult,
    normalize_cli_output,
    normalize_library_output,
    run_parity_test,
)

__all__ = [
    "ParityTest",
    "ParityTestResult",
    "normalize_cli_output",
    "normalize_library_output",
    "run_parity_test",
]
