"""Core parity testing framework.

This module provides the infrastructure for testing that the CLI and library
produce identical outputs when given the same inputs.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ragdiff.core.models import ComparisonResult, RagResult


@dataclass
class ParityTest:
    """Definition of a parity test case.

    Attributes:
        name: Human-readable test name
        description: Detailed description of what this test validates
        cli_command: List of CLI command arguments (without 'ragdiff' prefix)
        library_call: Function that returns library result
        expected_output_type: Type of expected output ('query', 'compare', 'batch')
        skip_llm_evaluation: Whether to skip LLM evaluation comparison (non-deterministic)
    """

    name: str
    description: str
    cli_command: list[str]
    library_call: callable
    expected_output_type: str
    skip_llm_evaluation: bool = True


@dataclass
class ParityTestResult:
    """Result of a parity test.

    Attributes:
        passed: Whether the test passed
        cli_output: Normalized CLI output
        library_output: Normalized library output
        differences: List of differences found (empty if passed)
        error: Error message if test failed to run
    """

    passed: bool
    cli_output: Optional[dict] = None
    library_output: Optional[dict] = None
    differences: list[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.differences is None:
            self.differences = []


def normalize_rag_result(result: dict | RagResult) -> dict:
    """Normalize a RagResult to a comparable dict.

    Args:
        result: Either a dict (from CLI JSON) or RagResult object (from library)

    Returns:
        Normalized dictionary with consistent structure

    Example:
        >>> from ragdiff.core.models import RagResult
        >>> result = RagResult(id="1", text="test", score=0.95, source="src")
        >>> norm = normalize_rag_result(result)
        >>> norm['id']
        '1'
    """
    if isinstance(result, RagResult):
        return {
            "id": result.id,
            "text": result.text,
            "score": result.score,
            "source": result.source,
            "metadata": result.metadata,
        }
    elif isinstance(result, dict):
        # Already a dict from CLI JSON
        return {
            "id": result.get("id"),
            "text": result.get("text"),
            "score": result.get("score"),
            "source": result.get("source"),
            "metadata": result.get("metadata"),
        }
    else:
        raise TypeError(f"Expected RagResult or dict, got {type(result)}")


def normalize_comparison_result(result: dict | ComparisonResult) -> dict:
    """Normalize a ComparisonResult to a comparable dict.

    Args:
        result: Either a dict (from CLI JSON) or ComparisonResult object (from library)

    Returns:
        Normalized dictionary with consistent structure
    """
    if isinstance(result, ComparisonResult):
        normalized = {
            "query": result.query,
            "timestamp": result.timestamp.isoformat(),
            "tool_results": {},
            "errors": result.errors,
        }

        # Normalize tool results
        for tool_name, results in result.tool_results.items():
            normalized["tool_results"][tool_name] = [
                normalize_rag_result(r) for r in results
            ]

        # Optionally include LLM evaluation (but usually skipped)
        if result.llm_evaluation:
            normalized["llm_evaluation"] = {
                "llm_model": result.llm_evaluation.llm_model,
                "winner": result.llm_evaluation.winner,
                "analysis": result.llm_evaluation.analysis,
                "quality_scores": result.llm_evaluation.quality_scores,
            }

        return normalized

    elif isinstance(result, dict):
        # Already a dict from CLI JSON - just ensure consistent structure
        normalized = {
            "query": result.get("query"),
            "timestamp": result.get("timestamp"),
            "tool_results": {},
            "errors": result.get("errors", {}),
        }

        # Normalize tool results
        if "tool_results" in result:
            for tool_name, results in result["tool_results"].items():
                normalized["tool_results"][tool_name] = [
                    normalize_rag_result(r) for r in results
                ]

        # LLM evaluation if present
        if "llm_evaluation" in result and result["llm_evaluation"]:
            llm_eval = result["llm_evaluation"]
            normalized["llm_evaluation"] = {
                "llm_model": llm_eval.get("llm_model"),
                "winner": llm_eval.get("winner"),
                "analysis": llm_eval.get("analysis"),
                "quality_scores": llm_eval.get("quality_scores", {}),
            }

        return normalized

    else:
        raise TypeError(f"Expected ComparisonResult or dict, got {type(result)}")


def normalize_cli_output(cli_json: str | dict, output_type: str) -> dict:
    """Normalize CLI JSON output to a comparable format.

    Args:
        cli_json: JSON string or dict from CLI output
        output_type: Type of output ('query', 'compare', 'batch')

    Returns:
        Normalized dictionary

    Example:
        >>> cli_output = '{"query": "test", "results": [...]}'
        >>> norm = normalize_cli_output(cli_output, "query")
        >>> 'results' in norm
        True
    """
    if isinstance(cli_json, str):
        data = json.loads(cli_json)
    else:
        data = cli_json

    if output_type == "query":
        # Single query output: {query, tool, results}
        return {
            "query": data.get("query"),
            "tool": data.get("tool"),
            "results": [normalize_rag_result(r) for r in data.get("results", [])],
        }

    elif output_type == "compare":
        # Comparison output: ComparisonResult structure
        return normalize_comparison_result(data)

    elif output_type == "batch":
        # Batch output: list of ComparisonResults
        if isinstance(data, list):
            return [normalize_comparison_result(r) for r in data]
        else:
            raise ValueError(f"Expected list for batch output, got {type(data)}")

    else:
        raise ValueError(f"Unknown output type: {output_type}")


def normalize_library_output(library_result: Any, output_type: str) -> dict:
    """Normalize library API output to a comparable format.

    Args:
        library_result: Result from library API call
        output_type: Type of output ('query', 'compare', 'batch')

    Returns:
        Normalized dictionary

    Example:
        >>> from ragdiff import query
        >>> results = query("config.yaml", "test", tool="vectara")
        >>> norm = normalize_library_output(results, "query")
        >>> 'results' in norm
        True
    """
    if output_type == "query":
        # library returns list[RagResult]
        if not isinstance(library_result, list):
            raise TypeError(f"Expected list[RagResult], got {type(library_result)}")

        return {
            "results": [normalize_rag_result(r) for r in library_result],
        }

    elif output_type == "compare":
        # library returns ComparisonResult
        if not isinstance(library_result, ComparisonResult):
            raise TypeError(f"Expected ComparisonResult, got {type(library_result)}")

        return normalize_comparison_result(library_result)

    elif output_type == "batch":
        # library returns list[ComparisonResult]
        if not isinstance(library_result, list):
            raise TypeError(
                f"Expected list[ComparisonResult], got {type(library_result)}"
            )

        return [normalize_comparison_result(r) for r in library_result]

    else:
        raise ValueError(f"Unknown output type: {output_type}")


def run_cli_command(command: list[str], config_path: Path) -> str:
    """Run a CLI command and return its JSON output.

    Args:
        command: List of command arguments (without 'ragdiff' prefix)
        config_path: Path to config file

    Returns:
        JSON output string from CLI

    Raises:
        subprocess.CalledProcessError: If CLI command fails
    """
    # Construct full command
    full_command = ["uv", "run", "ragdiff"] + command

    # Replace {config} placeholder with actual path
    full_command = [
        str(config_path) if arg == "{config}" else arg for arg in full_command
    ]

    # Run command
    result = subprocess.run(
        full_command,
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent.parent,  # Run from project root
    )

    return result.stdout


def compare_normalized_outputs(
    cli_output: dict,
    library_output: dict,
    skip_llm_evaluation: bool = True,
    skip_timestamps: bool = True,
) -> list[str]:
    """Compare two normalized outputs and return list of differences.

    Args:
        cli_output: Normalized CLI output
        library_output: Normalized library output
        skip_llm_evaluation: Skip comparing LLM evaluations (non-deterministic)
        skip_timestamps: Skip comparing timestamps (always different)

    Returns:
        List of difference descriptions (empty if outputs match)

    Example:
        >>> cli = {"query": "test", "results": []}
        >>> lib = {"query": "test", "results": []}
        >>> diffs = compare_normalized_outputs(cli, lib)
        >>> len(diffs)
        0
    """
    differences = []

    def compare_values(path: str, cli_val: Any, lib_val: Any):
        """Recursively compare values and record differences."""
        # Skip certain fields
        if skip_timestamps and "timestamp" in path:
            return
        if skip_llm_evaluation and "llm_evaluation" in path:
            return

        # Handle None
        if cli_val is None and lib_val is None:
            return
        if cli_val is None or lib_val is None:
            differences.append(f"{path}: CLI={repr(cli_val)}, Library={repr(lib_val)}")
            return

        # Handle different types
        if not isinstance(cli_val, type(lib_val)) and not isinstance(
            lib_val, type(cli_val)
        ):
            differences.append(
                f"{path}: Different types - CLI={type(cli_val).__name__}, "
                f"Library={type(lib_val).__name__}"
            )
            return

        # Handle dicts
        if isinstance(cli_val, dict):
            all_keys = set(cli_val.keys()) | set(lib_val.keys())
            for key in all_keys:
                compare_values(
                    f"{path}.{key}",
                    cli_val.get(key),
                    lib_val.get(key),
                )
            return

        # Handle lists
        if isinstance(cli_val, list):
            if len(cli_val) != len(lib_val):
                differences.append(
                    f"{path}: Different lengths - CLI={len(cli_val)}, "
                    f"Library={len(lib_val)}"
                )
                return

            for i, (cli_item, lib_item) in enumerate(zip(cli_val, lib_val)):
                compare_values(f"{path}[{i}]", cli_item, lib_item)
            return

        # Handle primitives
        if cli_val != lib_val:
            differences.append(f"{path}: CLI={repr(cli_val)}, Library={repr(lib_val)}")

    # Start comparison
    compare_values("root", cli_output, library_output)
    return differences


def run_parity_test(
    test: ParityTest,
    config_path: Path,
) -> ParityTestResult:
    """Run a single parity test.

    Args:
        test: ParityTest definition
        config_path: Path to config file

    Returns:
        ParityTestResult with comparison results

    Example:
        >>> test = ParityTest(
        ...     name="test_query",
        ...     description="Test query command",
        ...     cli_command=["query", "test", "--tool", "vectara", "--format", "json"],
        ...     library_call=lambda: query("config.yaml", "test", tool="vectara"),
        ...     expected_output_type="query"
        ... )
        >>> result = run_parity_test(test, Path("config.yaml"))
        >>> result.passed
        True
    """
    try:
        # Run CLI command
        cli_output_raw = run_cli_command(test.cli_command, config_path)
        cli_output_normalized = normalize_cli_output(
            cli_output_raw, test.expected_output_type
        )

        # Run library call
        library_result = test.library_call()
        library_output_normalized = normalize_library_output(
            library_result, test.expected_output_type
        )

        # Compare outputs
        differences = compare_normalized_outputs(
            cli_output_normalized,
            library_output_normalized,
            skip_llm_evaluation=test.skip_llm_evaluation,
        )

        return ParityTestResult(
            passed=len(differences) == 0,
            cli_output=cli_output_normalized,
            library_output=library_output_normalized,
            differences=differences,
        )

    except Exception as e:
        return ParityTestResult(
            passed=False,
            error=str(e),
        )
