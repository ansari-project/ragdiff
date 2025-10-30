"""Comparison module for RAG provider evaluation.

v2.0: Domain-based comparison with LLM evaluation.
"""

from .evaluator import compare_runs
from .reference_evaluator import evaluate_run

__all__ = ["compare_runs", "evaluate_run"]
