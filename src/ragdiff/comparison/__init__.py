"""Comparison module for RAG tool evaluation.

v1.x: ComparisonEngine (deprecated)
v2.0: compare_runs function, evaluate_run function (reference-based)
"""

from .engine import ComparisonEngine  # v1.x
from .evaluator import compare_runs  # v2.0
from .reference_evaluator import evaluate_run  # v2.0 reference-based

__all__ = ["ComparisonEngine", "compare_runs", "evaluate_run"]
