"""Parity tests ensuring CLI and library produce identical outputs.

These tests verify that the library API and CLI produce the same results
when given identical inputs. This ensures consistency across both interfaces.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ragdiff import query
from ragdiff.core.models import RagResult

# Test fixtures - mock data that will be returned by both CLI and library
MOCK_RESULTS_TOOL1 = [
    RagResult(
        id="result-1",
        text="This is the first mock result for testing parity",
        score=0.95,
        source="Mock Source 1",
        metadata={"key": "value1"},
    ),
    RagResult(
        id="result-2",
        text="This is the second mock result",
        score=0.85,
        source="Mock Source 2",
        metadata={"key": "value2"},
    ),
]

MOCK_RESULTS_TOOL2 = [
    RagResult(
        id="result-3",
        text="First result from second tool",
        score=0.90,
        source="Tool2 Source",
        metadata=None,
    ),
]


def normalize_rag_result_for_comparison(result: dict) -> dict:
    """Normalize a RagResult dict for comparison.

    Handles minor differences like None vs missing keys.
    """
    return {
        "id": result.get("id"),
        "text": result.get("text"),
        "score": result.get("score"),
        "source": result.get("source"),
        "metadata": result.get("metadata"),
    }


def normalize_comparison_result(result: dict, skip_timestamp: bool = True) -> dict:
    """Normalize comparison result for comparison.

    Args:
        result: Comparison result dict
        skip_timestamp: Skip timestamp field (always different between runs)

    Returns:
        Normalized dict
    """
    normalized = {
        "query": result.get("query"),
        "tool_results": {},
        "errors": result.get("errors", {}),
    }

    # Normalize tool results
    if "tool_results" in result:
        for tool_name, results in result["tool_results"].items():
            normalized["tool_results"][tool_name] = [
                normalize_rag_result_for_comparison(r) for r in results
            ]

    # Skip timestamp by default (always different)
    if not skip_timestamp and "timestamp" in result:
        normalized["timestamp"] = result["timestamp"]

    return normalized


class TestQueryParity:
    """Test parity between CLI query command and library query() function."""

    @pytest.mark.skip(
        reason="Requires CLI refactoring to support JSON output for query command"
    )
    def test_query_basic_parity(self, tmp_path):
        """Test that CLI and library produce identical query results."""
        # Create test config
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
tools:
  test_tool:
    api_key_env: FAKE_KEY
    base_url: http://fake.local
"""
        )

        # Mock the adapter to return controlled results
        with patch("ragdiff.adapters.factory.create_adapter") as mock_create:
            mock_adapter = MagicMock()
            mock_adapter.search.return_value = MOCK_RESULTS_TOOL1
            mock_create.return_value = mock_adapter

            # Run library query
            library_results = query(
                str(config_file),
                "test query",
                tool="test_tool",
                top_k=5,
            )

        # Run CLI query
        cli_result = subprocess.run(
            [
                "uv",
                "run",
                "ragdiff",
                "query",
                "test query",
                "--tool",
                "test_tool",
                "--config",
                str(config_file),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Parse CLI output
        cli_data = json.loads(cli_result.stdout)

        # Normalize for comparison
        library_normalized = [
            {
                "id": r.id,
                "text": r.text,
                "score": r.score,
                "source": r.source,
                "metadata": r.metadata,
            }
            for r in library_results
        ]

        cli_normalized = [
            normalize_rag_result_for_comparison(r) for r in cli_data.get("results", [])
        ]

        # Compare
        assert library_normalized == cli_normalized


class TestCompareParity:
    """Test parity between CLI compare command and library compare() function."""

    @pytest.mark.skip(reason="Requires stable mock data for both CLI and library")
    def test_compare_basic_parity(self, tmp_path):
        """Test that CLI and library produce identical comparison results."""
        # This test is skipped because it requires complex mocking
        # to ensure both CLI and library get the same mock data
        pass


class TestBatchParity:
    """Test parity between CLI batch/run command and library run_batch() function."""

    @pytest.mark.skip(reason="Requires stable mock data and CLI refactoring")
    def test_batch_basic_parity(self, tmp_path):
        """Test that CLI and library produce identical batch results."""
        pass


class TestNormalizationFunctions:
    """Test the normalization functions used for parity testing."""

    def test_normalize_rag_result(self):
        """Test RagResult normalization."""
        result_dict = {
            "id": "test-1",
            "text": "test text",
            "score": 0.95,
            "source": "test source",
            "metadata": {"key": "value"},
        }

        normalized = normalize_rag_result_for_comparison(result_dict)

        assert normalized["id"] == "test-1"
        assert normalized["text"] == "test text"
        assert normalized["score"] == 0.95
        assert normalized["source"] == "test source"
        assert normalized["metadata"] == {"key": "value"}

    def test_normalize_rag_result_with_none(self):
        """Test RagResult normalization with None values."""
        result_dict = {
            "id": "test-1",
            "text": "test text",
            "score": 0.95,
            "source": None,
            "metadata": None,
        }

        normalized = normalize_rag_result_for_comparison(result_dict)

        assert normalized["source"] is None
        assert normalized["metadata"] is None

    def test_normalize_comparison_result(self):
        """Test ComparisonResult normalization."""
        comparison_dict = {
            "query": "test query",
            "timestamp": "2025-01-15T10:30:00",
            "tool_results": {
                "tool1": [
                    {
                        "id": "r1",
                        "text": "result 1",
                        "score": 0.95,
                        "source": "source1",
                        "metadata": None,
                    }
                ],
                "tool2": [
                    {
                        "id": "r2",
                        "text": "result 2",
                        "score": 0.90,
                        "source": "source2",
                        "metadata": {"key": "val"},
                    }
                ],
            },
            "errors": {},
        }

        normalized = normalize_comparison_result(comparison_dict)

        assert normalized["query"] == "test query"
        assert "timestamp" not in normalized  # Skipped by default
        assert len(normalized["tool_results"]["tool1"]) == 1
        assert len(normalized["tool_results"]["tool2"]) == 1
        assert normalized["tool_results"]["tool1"][0]["id"] == "r1"
        assert normalized["tool_results"]["tool2"][0]["metadata"] == {"key": "val"}


class TestParityFramework:
    """Test the parity testing framework itself."""

    def test_framework_exists(self):
        """Test that parity framework module exists and is importable."""
        try:
            from tests.parity.framework import (
                ParityTest,
                ParityTestResult,
                normalize_cli_output,
                normalize_library_output,
            )

            assert ParityTest is not None
            assert ParityTestResult is not None
            assert normalize_cli_output is not None
            assert normalize_library_output is not None
        except ImportError as e:
            pytest.fail(f"Failed to import parity framework: {e}")

    def test_parity_test_dataclass(self):
        """Test ParityTest dataclass construction."""
        from tests.parity.framework import ParityTest

        test = ParityTest(
            name="test_example",
            description="Example test",
            cli_command=["query", "test"],
            library_call=lambda: [],
            expected_output_type="query",
        )

        assert test.name == "test_example"
        assert test.description == "Example test"
        assert test.skip_llm_evaluation is True

    def test_parity_result_dataclass(self):
        """Test ParityTestResult dataclass construction."""
        from tests.parity.framework import ParityTestResult

        result = ParityTestResult(
            passed=True,
            cli_output={"test": "data"},
            library_output={"test": "data"},
            differences=[],
        )

        assert result.passed is True
        assert result.cli_output == {"test": "data"}
        assert result.differences == []


# Documentation test to explain parity testing approach
def test_parity_testing_documentation():
    """Document the parity testing approach.

    This test serves as documentation for how parity testing works in RAGDiff.

    Parity Testing Goals:
    1. Ensure CLI and library produce identical outputs for identical inputs
    2. Validate that both interfaces work consistently
    3. Catch regressions where one interface changes but not the other

    Approach:
    1. Create controlled test scenarios with mocked responses
    2. Run the same operation through CLI (subprocess) and library (direct call)
    3. Normalize outputs to handle minor format differences
    4. Compare normalized outputs for equality

    Challenges:
    - CLI and library have different output formats (text/JSON vs objects)
    - Timestamps and LLM evaluations are non-deterministic
    - External API calls need to be mocked for reproducibility

    Current Status:
    - Framework created (tests/parity/framework.py)
    - Normalization functions implemented
    - Test fixtures prepared
    - Actual parity tests marked as skipped pending CLI JSON output support

    Next Steps:
    1. Add --format json support to all CLI commands
    2. Implement comprehensive mocking for adapters
    3. Create 10+ parity test cases covering all adapter types
    4. Add parity tests to CI pipeline
    """
    # This test always passes - it's documentation
    assert True
