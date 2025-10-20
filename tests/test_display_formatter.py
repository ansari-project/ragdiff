"""Tests for display formatter."""

import json

import pytest

from src.core.models import ComparisonResult, LLMEvaluation, RagResult
from src.display.formatter import ComparisonFormatter


class TestComparisonFormatter:
    """Test comparison formatter functionality."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample comparison result."""
        return ComparisonResult(
            query="What is Islamic inheritance law?",
            tool_results={
                "goodmem": [
                    RagResult(
                        id="g1",
                        text="Islamic inheritance law, or Mirath, is a set of rules...",
                        score=0.95,
                        source="Fiqh Handbook",
                        latency_ms=125.5,
                    ),
                    RagResult(
                        id="g2",
                        text="The Quran provides specific guidance on inheritance...",
                        score=0.87,
                        source="Quran Commentary",
                    ),
                ],
                "mawsuah": [
                    RagResult(
                        id="m1",
                        text="In Islamic jurisprudence, inheritance follows strict rules...",
                        score=0.92,
                        source="Mawsuah Fiqhiyyah",
                        latency_ms=98.3,
                    )
                ],
            },
            errors={},
        )

    @pytest.fixture
    def result_with_errors(self):
        """Create result with errors."""
        return ComparisonResult(
            query="test query",
            tool_results={"goodmem": [RagResult(id="1", text="Result", score=0.9)]},
            errors={"mawsuah": "Connection timeout"},
        )

    @pytest.fixture
    def result_with_llm_eval(self):
        """Create result with LLM evaluation."""
        result = ComparisonResult(
            query="test query",
            tool_results={
                "goodmem": [RagResult(id="1", text="Good result", score=0.9)],
                "mawsuah": [RagResult(id="2", text="Better result", score=0.95)],
            },
            errors={},
        )
        result.llm_evaluation = LLMEvaluation(
            llm_model="claude-opus-4-1",
            winner="mawsuah",
            analysis="Mawsuah provides more comprehensive and accurate information.",
            quality_scores={"goodmem": 7, "mawsuah": 9},
            metadata={},
        )
        return result

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return ComparisonFormatter(width=80, indent=2)

    def test_initialization(self):
        """Test formatter initialization."""
        formatter = ComparisonFormatter(width=100, indent=4)
        assert formatter.width == 100
        assert formatter.indent_str == "    "

    def test_format_side_by_side(self, formatter, sample_result):
        """Test side-by-side formatting."""
        output = formatter.format_side_by_side(sample_result)

        # Check key sections are present
        assert "RAG TOOL COMPARISON RESULTS" in output
        assert "Query: What is Islamic inheritance law?" in output
        assert "[GOODMEM]" in output
        assert "[MAWSUAH]" in output
        assert "Score: 0.950" in output
        assert "Source: Fiqh Handbook" in output

    def test_format_with_errors(self, formatter, result_with_errors):
        """Test formatting with errors."""
        output = formatter.format_side_by_side(result_with_errors)

        assert "ERRORS:" in output
        assert "[mawsuah] Connection timeout" in output

    def test_format_with_llm_evaluation(self, formatter, result_with_llm_eval):
        """Test formatting with LLM evaluation."""
        output = formatter.format_side_by_side(result_with_llm_eval)

        assert "LLM EVALUATION:" in output
        assert "Model: claude-opus-4-1" in output
        assert "Winner: mawsuah" in output
        assert "provides more comprehensive" in output
        assert "goodmem: 7/10" in output
        assert "mawsuah: 9/10" in output

    def test_format_json(self, formatter, sample_result):
        """Test JSON formatting."""
        json_output = formatter.format_json(sample_result, pretty=True)
        data = json.loads(json_output)

        assert data["query"] == "What is Islamic inheritance law?"
        assert "goodmem" in data["tool_results"]
        assert len(data["tool_results"]["goodmem"]) == 2
        assert data["tool_results"]["goodmem"][0]["score"] == 0.95

    def test_format_json_compact(self, formatter, sample_result):
        """Test compact JSON formatting."""
        json_output = formatter.format_json(sample_result, pretty=False)
        assert "\n" not in json_output
        data = json.loads(json_output)
        assert data["query"] == "What is Islamic inheritance law?"

    def test_format_markdown(self, formatter, sample_result):
        """Test Markdown formatting."""
        md_output = formatter.format_markdown(sample_result)

        # Check Markdown elements
        assert "# RAG Tool Comparison Results" in md_output
        assert "**Query:**" in md_output
        assert "### GOODMEM" in md_output
        assert "### MAWSUAH" in md_output
        assert "| Tool | Results | Latency |" in md_output
        assert "| goodmem | 2 | 125.5ms |" in md_output

    def test_format_markdown_with_llm(self, formatter, result_with_llm_eval):
        """Test Markdown with LLM evaluation."""
        md_output = formatter.format_markdown(result_with_llm_eval)

        assert "## LLM Evaluation" in md_output
        assert "**Winner:** mawsuah" in md_output
        assert "| Tool | Score |" in md_output
        assert "| goodmem | 7/10 |" in md_output

    def test_format_summary(self, formatter, sample_result):
        """Test summary formatting."""
        summary = formatter.format_summary(sample_result)

        assert "Query: What is Islamic inheritance law?" in summary
        assert "goodmem: 2" in summary
        assert "mawsuah: 1" in summary

    def test_format_summary_with_errors(self, formatter, result_with_errors):
        """Test summary with errors."""
        summary = formatter.format_summary(result_with_errors)

        assert "Errors: mawsuah" in summary

    def test_format_summary_with_winner(self, formatter, result_with_llm_eval):
        """Test summary with LLM winner."""
        summary = formatter.format_summary(result_with_llm_eval)

        assert "Winner: mawsuah" in summary

    def test_text_wrapping(self, formatter):
        """Test long text wrapping."""
        long_text = "This is a very long text that should be wrapped " * 10
        result = ComparisonResult(
            query="test",
            tool_results={"tool1": [RagResult(id="1", text=long_text, score=0.9)]},
            errors={},
        )

        output = formatter.format_side_by_side(result)
        lines = output.split("\n")

        # Check that no line exceeds the width limit (except headers)
        for line in lines:
            if not line.startswith("=") and not line.startswith("-"):
                assert len(line) <= formatter.width + 10  # Allow some margin

    def test_empty_results(self, formatter):
        """Test formatting with empty results."""
        result = ComparisonResult(
            query="test", tool_results={"tool1": [], "tool2": []}, errors={}
        )

        output = formatter.format_side_by_side(result)
        assert "Results: 0" in output

    def test_performance_metrics(self, formatter, sample_result):
        """Test performance metrics formatting."""
        output = formatter.format_side_by_side(sample_result)

        assert "PERFORMANCE METRICS:" in output
        assert "[goodmem] Results: 2, Latency: 125.5ms" in output
        assert "[mawsuah] Results: 1, Latency: 98.3ms" in output

    def test_no_latency_data(self, formatter):
        """Test formatting when latency data is missing."""
        result = ComparisonResult(
            query="test",
            tool_results={"tool1": [RagResult(id="1", text="Result", score=0.9)]},
            errors={},
        )

        output = formatter.format_side_by_side(result)
        assert "Latency:" not in output  # Should not show latency if not available
