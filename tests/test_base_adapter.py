"""Tests for base adapter."""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.adapters.base import BaseRagTool
from src.core.models import ToolConfig, RagResult


class ConcreteRagTool(BaseRagTool):
    """Concrete implementation for testing."""

    def search(self, query: str, top_k: int = 5):
        """Mock search implementation."""
        return [
            RagResult(
                id=f"doc{i}",
                text=f"Result {i} for query: {query}",
                score=0.9 - (i * 0.1)
            )
            for i in range(min(top_k, 3))
        ]


class TestBaseRagTool:
    """Test BaseRagTool adapter."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="test_tool",
            api_key_env="TEST_API_KEY",
            corpus_id="test_corpus",
            base_url="https://test.api.com",
            timeout=30,
            max_retries=3,
            default_top_k=5
        )

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_initialization(self, tool_config):
        """Test tool initialization."""
        tool = ConcreteRagTool(tool_config)
        assert tool.name == "test_tool"
        assert tool.timeout == 30
        assert tool.default_top_k == 5

    def test_missing_api_key(self, tool_config):
        """Test error when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variable"):
                ConcreteRagTool(tool_config)

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_run_success(self, tool_config):
        """Test successful run method."""
        tool = ConcreteRagTool(tool_config)
        result = tool.run("test query", top_k=2)

        assert result["success"] is True
        assert result["query"] == "test query"
        assert len(result["results"]) == 2
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_run_with_error(self, tool_config):
        """Test run method with error."""
        tool = ConcreteRagTool(tool_config)

        # Mock search to raise an exception
        with patch.object(tool, 'search', side_effect=Exception("API Error")):
            result = tool.run("test query")

            assert result["success"] is False
            assert "error" in result
            assert "API Error" in result["error"]
            assert result["results"] == []

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_format_as_tool_result_success(self, tool_config):
        """Test formatting successful results."""
        tool = ConcreteRagTool(tool_config)
        results = {
            "success": True,
            "results": [
                RagResult(id="1", text="First result text that is quite long and should be truncated", score=0.95),
                RagResult(id="2", text="Second result", score=0.85)
            ]
        }

        formatted = tool.format_as_tool_result(results)
        assert "1. [0.95]" in formatted
        assert "2. [0.85]" in formatted
        assert "..." in formatted  # Text should be truncated

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_format_as_tool_result_error(self, tool_config):
        """Test formatting error results."""
        tool = ConcreteRagTool(tool_config)
        results = {
            "success": False,
            "error": "Connection timeout"
        }

        formatted = tool.format_as_tool_result(results)
        assert "Error:" in formatted
        assert "Connection timeout" in formatted

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_format_as_tool_result_empty(self, tool_config):
        """Test formatting empty results."""
        tool = ConcreteRagTool(tool_config)
        results = {
            "success": True,
            "results": []
        }

        formatted = tool.format_as_tool_result(results)
        assert formatted == "No results found."

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key_123"})
    def test_score_normalization(self, tool_config):
        """Test score normalization."""
        tool = ConcreteRagTool(tool_config)

        assert tool._normalize_score(0.5) == 0.5
        assert tool._normalize_score(95) == 0.95
        assert tool._normalize_score(850) == 0.85
        assert tool._normalize_score(-0.1) == 0
        assert tool._normalize_score(1200) == 1.0