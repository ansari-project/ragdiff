"""Tests for CLI functionality."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from ragdiff.cli import app
from ragdiff.comparison.engine import ComparisonEngine
from ragdiff.core.models import ComparisonResult, RagResult


class TestCLIStatsDisplay:
    """Test CLI stats display functions."""

    def test_get_summary_stats_format(self):
        """Test that get_summary_stats returns expected format."""

        # Create mock results
        results = {
            "vectara": [
                RagResult(id="1", text="Result 1", score=0.9, source="vectara"),
                RagResult(id="2", text="Result 2", score=0.8, source="vectara"),
            ],
            "agentset": [
                RagResult(id="3", text="Result 3", score=0.7, source="agentset"),
            ],
        }

        comparison_result = ComparisonResult(
            query="test query", tool_results=results, errors={}
        )

        # Create engine with mock tools
        mock_tool = MagicMock()
        engine = ComparisonEngine(tools={"vectara": mock_tool})
        stats = engine.get_summary_stats(comparison_result)

        # Verify the structure returned by get_summary_stats
        assert "query" in stats
        assert "tools_compared" in stats
        assert "result_counts" in stats
        assert "average_scores" in stats
        assert "latencies_ms" in stats

        # Verify data types
        assert isinstance(stats["tools_compared"], list)
        assert isinstance(stats["result_counts"], dict)
        assert isinstance(stats["average_scores"], dict)
        assert isinstance(stats["latencies_ms"], dict)

        # Verify content
        assert "vectara" in stats["tools_compared"]
        assert "agentset" in stats["tools_compared"]
        assert stats["result_counts"]["vectara"] == 2
        assert stats["result_counts"]["agentset"] == 1
        assert abs(stats["average_scores"]["vectara"] - 0.85) < 0.001  # (0.9 + 0.8) / 2

    def test_stats_transformation_for_display(self):
        """Test transformation of stats for CLI display."""
        # This is the format returned by get_summary_stats
        raw_stats = {
            "query": "test",
            "tools_compared": ["vectara", "agentset"],
            "tools_with_errors": [],
            "result_counts": {"vectara": 5, "agentset": 3},
            "average_scores": {"vectara": 0.75, "agentset": 0.60},
            "latencies_ms": {"vectara": 100.5, "agentset": 200.3},
        }

        # This is the transformation that CLI does
        stats = {}
        for tool in raw_stats.get("tools_compared", []):
            stats[tool] = {
                "count": raw_stats.get("result_counts", {}).get(tool, 0),
                "avg_score": raw_stats.get("average_scores", {}).get(tool, 0),
                "latency_ms": raw_stats.get("latencies_ms", {}).get(tool, 0),
            }

        # Verify the transformed format
        assert "vectara" in stats
        assert "agentset" in stats

        # Verify vectara stats
        assert isinstance(stats["vectara"], dict)
        assert stats["vectara"]["count"] == 5
        assert stats["vectara"]["avg_score"] == 0.75
        assert stats["vectara"]["latency_ms"] == 100.5

        # Verify agentset stats
        assert isinstance(stats["agentset"], dict)
        assert stats["agentset"]["count"] == 3
        assert stats["agentset"]["avg_score"] == 0.60
        assert stats["agentset"]["latency_ms"] == 200.3

        # Verify each value can be accessed with .get()
        for _tool_name, tool_stats in stats.items():
            # This should not raise AttributeError
            count = tool_stats.get("count", 0)
            avg_score = tool_stats.get("avg_score", 0)
            latency = tool_stats.get("latency_ms", 0)

            assert isinstance(count, (int, float))
            assert isinstance(avg_score, (int, float))
            assert isinstance(latency, (int, float))

    def test_stats_transformation_handles_missing_tools(self):
        """Test transformation handles tools with missing stats."""
        raw_stats = {
            "query": "test",
            "tools_compared": ["vectara", "agentset"],
            "tools_with_errors": ["agentset"],
            "result_counts": {"vectara": 5},  # agentset missing
            "average_scores": {"vectara": 0.75},  # agentset missing
            "latencies_ms": {},  # both missing
        }

        # Transform stats
        stats = {}
        for tool in raw_stats.get("tools_compared", []):
            stats[tool] = {
                "count": raw_stats.get("result_counts", {}).get(tool, 0),
                "avg_score": raw_stats.get("average_scores", {}).get(tool, 0),
                "latency_ms": raw_stats.get("latencies_ms", {}).get(tool, 0),
            }

        # Verify defaults are used for missing data
        assert stats["vectara"]["count"] == 5
        assert stats["vectara"]["avg_score"] == 0.75
        assert stats["vectara"]["latency_ms"] == 0  # missing

        assert stats["agentset"]["count"] == 0  # missing
        assert stats["agentset"]["avg_score"] == 0  # missing
        assert stats["agentset"]["latency_ms"] == 0  # missing

    def test_stats_values_are_not_strings(self):
        """Test that stats values are dicts, not strings."""
        raw_stats = {
            "query": "test",
            "tools_compared": ["vectara"],
            "result_counts": {"vectara": 5},
            "average_scores": {"vectara": 0.75},
            "latencies_ms": {"vectara": 100.5},
        }

        stats = {}
        for tool in raw_stats.get("tools_compared", []):
            stats[tool] = {
                "count": raw_stats.get("result_counts", {}).get(tool, 0),
                "avg_score": raw_stats.get("average_scores", {}).get(tool, 0),
                "latency_ms": raw_stats.get("latencies_ms", {}).get(tool, 0),
            }

        # Verify tool_stats is a dict, not a string
        for _tool_name, tool_stats in stats.items():
            assert isinstance(
                tool_stats, dict
            ), f"tool_stats should be dict, got {type(tool_stats)}"
            assert not isinstance(
                tool_stats, str
            ), "tool_stats should never be a string"

            # Verify calling .get() works (would fail if tool_stats was a string)
            try:
                tool_stats.get("count", 0)
                tool_stats.get("avg_score", 0)
                tool_stats.get("latency_ms", 0)
            except AttributeError as e:
                pytest.fail(
                    f"tool_stats.get() raised AttributeError: {e}. "
                    f"tool_stats type: {type(tool_stats)}"
                )


class TestAgentsetAdapter:
    """Test Agentset adapter has required methods."""

    def test_agentset_has_normalize_score(self):
        """Test that AgentsetAdapter has _normalize_score method."""
        from ragdiff.adapters.agentset import AgentsetAdapter

        # Check method exists
        assert hasattr(AgentsetAdapter, "_normalize_score")

        # Check it's callable
        assert callable(AgentsetAdapter._normalize_score)

    def test_normalize_score_returns_float(self):
        """Test _normalize_score returns correct values."""
        from ragdiff.adapters.agentset import AgentsetAdapter
        from ragdiff.core.models import ToolConfig

        # Create adapter with mock config
        config = ToolConfig(
            name="agentset",
            api_key_env="AGENTSET_API_TOKEN",
            namespace_id_env="AGENTSET_NAMESPACE_ID",
        )

        # Mock the credentials to avoid needing real env vars
        adapter = AgentsetAdapter.__new__(AgentsetAdapter)
        adapter.config = config
        adapter._credentials = {}

        # Test normalization
        assert adapter._normalize_score(0.5) == 0.5  # Already normalized
        assert adapter._normalize_score(75.0) == 0.75  # Percentage
        assert adapter._normalize_score(750.0) == 0.75  # Out of 1000
        assert adapter._normalize_score(-0.1) == 0.0  # Clamp negative


class TestCLICommands:
    """Test CLI command structure and basic functionality."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_query_command_validates_tool_requirement(self, runner):
        """Test query command requires at least one tool."""
        result = runner.invoke(app, ["query", "test query"])

        # Should fail without a tool specified
        assert result.exit_code != 0
        assert "At least one tool must be specified" in result.stdout

    def test_query_command_has_correct_signature(self):
        """Test that query command has expected parameters."""
        from inspect import signature

        from ragdiff.cli import query

        sig = signature(query)
        params = list(sig.parameters.keys())

        # Verify required and key parameters exist
        assert "query_text" in params
        assert "tools" in params
        assert "config_file" in params
        assert "top_k" in params
        assert "evaluate" in params
        assert "output_file" in params
        assert "output_format" in params

    def test_run_command_has_correct_signature(self):
        """Test that run command has expected parameters."""
        from inspect import signature

        from ragdiff.cli import run

        sig = signature(run)
        params = list(sig.parameters.keys())

        # Verify required and key parameters exist
        assert "queries_file" in params
        assert "config_file" in params
        assert "tools" in params
        assert "top_k" in params
        assert "output_dir" in params
        assert "output_format" in params

    def test_compare_command_has_correct_signature(self):
        """Test that compare command has expected parameters."""
        from inspect import signature

        from ragdiff.cli import compare

        sig = signature(compare)
        params = list(sig.parameters.keys())

        # Verify required and key parameters exist
        assert "results_dir" in params
        assert "output_file" in params
        assert "output_format" in params

    def test_three_commands_exist(self):
        """Test that all three main commands are registered."""
        from typer.main import get_command

        cli = get_command(app)
        commands = cli.list_commands(None)

        # Verify the three main commands exist
        assert "query" in commands
        assert "run" in commands
        assert "compare" in commands
