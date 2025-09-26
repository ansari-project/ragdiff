"""Tests for data models."""

import pytest
from datetime import datetime
from src.core.models import (
    RagResult,
    ComparisonOutcome,
    LLMEvaluation,
    ComparisonResult,
    ToolConfig
)


class TestRagResult:
    """Test RagResult model."""

    def test_valid_creation(self):
        """Test creating valid RagResult."""
        result = RagResult(
            id="doc1",
            text="Sample text",
            score=0.95,
            source="source1"
        )
        assert result.id == "doc1"
        assert result.text == "Sample text"
        assert result.score == 0.95
        assert result.source == "source1"

    def test_score_normalization(self):
        """Test score normalization."""
        # Score > 1 should be normalized
        result = RagResult(id="doc1", text="text", score=95)
        assert 0 <= result.score <= 1
        assert result.score == 0.95

        # Score > 100 should be normalized
        result = RagResult(id="doc2", text="text", score=850)
        assert result.score == 0.85

    def test_validation_errors(self):
        """Test validation errors."""
        with pytest.raises(ValueError, match="ID cannot be empty"):
            RagResult(id="", text="text", score=0.5)

        with pytest.raises(ValueError, match="text cannot be empty"):
            RagResult(id="doc1", text="", score=0.5)


class TestLLMEvaluation:
    """Test LLMEvaluation model."""

    def test_creation(self):
        """Test creating LLMEvaluation."""
        eval = LLMEvaluation(
            summary="Goodmem provides better coverage",
            winner=ComparisonOutcome.GOODMEM_BETTER,
            confidence="high",
            key_differences=["Better relevance", "More sources"],
            recommendations="Use goodmem for production"
        )
        assert eval.winner == ComparisonOutcome.GOODMEM_BETTER
        assert eval.confidence == "high"
        assert len(eval.key_differences) == 2

    def test_to_dict(self):
        """Test dictionary conversion."""
        eval = LLMEvaluation(
            summary="Test summary",
            winner=ComparisonOutcome.TIE,
            confidence="medium",
            key_differences=["diff1"],
            recommendations="test rec",
            strengths_goodmem=["strength1"],
            strengths_mawsuah=["strength2"]
        )

        result = eval.to_dict()
        assert result["winner"] == "tie"
        assert result["confidence"] == "medium"
        assert "strengths_goodmem" in result
        assert "strengths_mawsuah" in result


class TestComparisonResult:
    """Test ComparisonResult model."""

    def test_creation(self):
        """Test creating ComparisonResult."""
        result = ComparisonResult(
            query="test query",
            tool_results={
                "goodmem": [
                    RagResult(id="g1", text="result1", score=0.9)
                ],
                "mawsuah": [
                    RagResult(id="m1", text="result2", score=0.8)
                ]
            },
            errors={}
        )
        assert result.query == "test query"
        assert len(result.goodmem_results) == 1
        assert len(result.mawsuah_results) == 1

    def test_has_errors(self):
        """Test error detection."""
        result = ComparisonResult(
            query="test",
            tool_results={"goodmem": [], "mawsuah": []},
            errors={}
        )
        assert not result.has_errors()

        result.errors["goodmem"] = "API failed"
        assert result.has_errors()

    def test_get_result_counts(self):
        """Test result counting."""
        result = ComparisonResult(
            query="test",
            tool_results={
                "goodmem": [
                    RagResult(id=f"g{i}", text=f"text{i}", score=0.9)
                    for i in range(3)
                ],
                "mawsuah": [
                    RagResult(id=f"m{i}", text=f"text{i}", score=0.8)
                    for i in range(5)
                ]
            },
            errors={}
        )
        counts = result.get_result_counts()
        assert counts["goodmem"] == 3
        assert counts["mawsuah"] == 5

    def test_to_dict(self):
        """Test dictionary conversion."""
        goodmem_result = RagResult(id="g1", text="result1", score=0.9, latency_ms=150.5)
        result = ComparisonResult(
            query="test query",
            tool_results={
                "goodmem": [goodmem_result],
                "mawsuah": []
            },
            errors={"mawsuah": "Connection failed"}
        )

        dict_result = result.to_dict()
        assert dict_result["query"] == "test query"
        assert dict_result["tool_results"]["goodmem"][0]["id"] == "g1"
        assert dict_result["errors"]["mawsuah"] == "Connection failed"


class TestToolConfig:
    """Test ToolConfig model."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = ToolConfig(
            name="test_tool",
            api_key_env="TEST_API_KEY",
            base_url="https://api.test.com",
            timeout=60
        )
        assert config.name == "test_tool"
        assert config.timeout == 60
        config.validate()  # Should not raise

    def test_validation_errors(self):
        """Test configuration validation."""
        config = ToolConfig(name="", api_key_env="TEST")
        with pytest.raises(ValueError, match="Tool name is required"):
            config.validate()

        config = ToolConfig(name="test", api_key_env="")
        with pytest.raises(ValueError, match="API key environment variable"):
            config.validate()