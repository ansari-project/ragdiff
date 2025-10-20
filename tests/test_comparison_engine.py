"""Tests for comparison engine."""

import time
from unittest.mock import Mock

import pytest

from src.comparison.engine import ComparisonEngine
from src.core.models import ComparisonResult, RagResult


class TestComparisonEngine:
    """Test comparison engine functionality."""

    @pytest.fixture
    def mock_tool1(self):
        """Create first mock tool."""
        tool = Mock()
        tool.search.return_value = [
            RagResult(
                id="tool1_1",
                text="Result 1 from tool 1",
                score=0.9,
                source="Tool 1 Source",
            ),
            RagResult(
                id="tool1_2",
                text="Result 2 from tool 1",
                score=0.8,
                source="Tool 1 Source",
            ),
        ]
        return tool

    @pytest.fixture
    def mock_tool2(self):
        """Create second mock tool."""
        tool = Mock()
        tool.search.return_value = [
            RagResult(
                id="tool2_1",
                text="Result 1 from tool 2",
                score=0.95,
                source="Tool 2 Source",
            ),
            RagResult(
                id="tool2_2",
                text="Result 2 from tool 2",
                score=0.85,
                source="Tool 2 Source",
            ),
        ]
        return tool

    @pytest.fixture
    def engine(self, mock_tool1, mock_tool2):
        """Create engine with mock tools."""
        tools = {"tool1": mock_tool1, "tool2": mock_tool2}
        return ComparisonEngine(tools)

    def test_initialization(self, mock_tool1):
        """Test engine initialization."""
        tools = {"test": mock_tool1}
        engine = ComparisonEngine(tools)
        assert engine.tools == tools

    def test_initialization_empty_tools(self):
        """Test error with empty tools."""
        with pytest.raises(ValueError, match="At least one tool"):
            ComparisonEngine({})

    def test_run_comparison_sequential(self, engine, mock_tool1, mock_tool2):
        """Test sequential comparison."""
        result = engine.run_comparison("test query", top_k=3, parallel=False)

        # Verify structure
        assert isinstance(result, ComparisonResult)
        assert result.query == "test query"
        assert "tool1" in result.tool_results
        assert "tool2" in result.tool_results
        assert len(result.errors) == 0

        # Verify search was called
        mock_tool1.search.assert_called_once_with("test query", 3)
        mock_tool2.search.assert_called_once_with("test query", 3)

        # Verify results
        assert len(result.tool_results["tool1"]) == 2
        assert len(result.tool_results["tool2"]) == 2

    def test_run_comparison_parallel(self, engine, mock_tool1, mock_tool2):
        """Test parallel comparison."""
        result = engine.run_comparison("parallel test", top_k=5, parallel=True)

        # Verify structure
        assert isinstance(result, ComparisonResult)
        assert result.query == "parallel test"
        assert "tool1" in result.tool_results
        assert "tool2" in result.tool_results

        # Verify both tools were called
        mock_tool1.search.assert_called_once_with("parallel test", 5)
        mock_tool2.search.assert_called_once_with("parallel test", 5)

    def test_run_comparison_with_error(self, mock_tool1):
        """Test handling of tool errors."""
        # Create failing tool
        failing_tool = Mock()
        failing_tool.search.side_effect = RuntimeError("Search failed")

        tools = {"working": mock_tool1, "failing": failing_tool}
        engine = ComparisonEngine(tools)

        result = engine.run_comparison("test", parallel=False)

        # Working tool should have results
        assert "working" in result.tool_results
        assert len(result.tool_results["working"]) == 2

        # Failing tool should be in errors
        assert "failing" in result.errors
        assert "Search failed" in result.errors["failing"]

    def test_latency_measurement(self, mock_tool1):
        """Test that latency is measured."""

        # Add delay to mock
        def delayed_search(query, top_k):
            time.sleep(0.01)  # 10ms delay
            return [RagResult(id="1", text="Result", score=0.9)]

        mock_tool1.search.side_effect = delayed_search

        engine = ComparisonEngine({"tool1": mock_tool1})
        result = engine.run_comparison("test")

        # Check latency was added
        assert result.tool_results["tool1"][0].latency_ms is not None
        assert result.tool_results["tool1"][0].latency_ms >= 10

    def test_get_summary_stats(self, engine):
        """Test summary statistics generation."""
        result = engine.run_comparison("test query", top_k=2)
        stats = engine.get_summary_stats(result)

        assert stats["query"] == "test query"
        assert set(stats["tools_compared"]) == {"tool1", "tool2"}
        assert stats["tools_with_errors"] == []
        assert stats["result_counts"]["tool1"] == 2
        assert stats["result_counts"]["tool2"] == 2

        # Check average scores
        assert 0.8 <= stats["average_scores"]["tool1"] <= 0.9
        assert 0.85 <= stats["average_scores"]["tool2"] <= 0.95

    def test_get_summary_stats_with_errors(self, mock_tool1):
        """Test summary stats with tool errors."""
        failing_tool = Mock()
        failing_tool.search.side_effect = RuntimeError("Failed")

        engine = ComparisonEngine({"working": mock_tool1, "failing": failing_tool})

        result = engine.run_comparison("test")
        stats = engine.get_summary_stats(result)

        assert "working" in stats["tools_compared"]
        assert "failing" in stats["tools_with_errors"]
        assert "working" in stats["result_counts"]
        assert "failing" not in stats["result_counts"]

    def test_parallel_error_handling(self):
        """Test error handling in parallel mode."""
        # Create mix of working and failing tools
        working_tool = Mock()
        working_tool.search.return_value = [
            RagResult(id="w1", text="Working", score=0.9)
        ]

        failing_tool = Mock()
        failing_tool.search.side_effect = ValueError("Tool error")

        engine = ComparisonEngine({"working": working_tool, "failing": failing_tool})

        result = engine.run_comparison("test", parallel=True)

        # Should have results from working tool
        assert "working" in result.tool_results
        assert len(result.tool_results["working"]) == 1

        # Should have error from failing tool
        assert "failing" in result.errors
        assert "Tool error" in result.errors["failing"]

    def test_single_tool_comparison(self, mock_tool1):
        """Test comparison with single tool."""
        engine = ComparisonEngine({"solo": mock_tool1})
        result = engine.run_comparison("single tool test")

        assert len(result.tool_results) == 1
        assert "solo" in result.tool_results
        assert len(result.tool_results["solo"]) == 2
