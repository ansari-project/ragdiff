"""Comparison module for RAG tool evaluation.

v1.x: ComparisonEngine (deprecated)
v2.0: compare_runs function
"""

from .engine import ComparisonEngine  # v1.x
from .evaluator import compare_runs  # v2.0

__all__ = ["ComparisonEngine", "compare_runs"]
