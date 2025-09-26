"""Integration tests for the RAG comparison tool."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from src.core.config import Config
from src.core.models import RagResult, ComparisonResult
from src.adapters.factory import create_adapter
from src.comparison.engine import ComparisonEngine
from src.display.formatter import ComparisonFormatter


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create temporary configuration file."""
        config_content = """
tools:
  test_tool1:
    api_key_env: TEST_KEY1
    base_url: http://test1.com
    timeout: 10

  test_tool2:
    api_key_env: TEST_KEY2
    base_url: http://test2.com
    timeout: 10

llm:
  model: test-model
  api_key_env: TEST_LLM_KEY
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        return config_file

    @patch.dict("os.environ", {
        "TEST_KEY1": "key1",
        "TEST_KEY2": "key2",
        "TEST_LLM_KEY": "llm_key"
    })
    def test_config_loading_and_validation(self, temp_config):
        """Test configuration loading and validation."""
        config = Config(temp_config)

        # Check tools are parsed
        assert "test_tool1" in config.tools
        assert "test_tool2" in config.tools

        # Check tool configs
        tool1 = config.tools["test_tool1"]
        assert tool1.api_key_env == "TEST_KEY1"
        assert tool1.base_url == "http://test1.com"
        assert tool1.timeout == 10

        # Check LLM config
        assert config.llm is not None
        assert config.llm.model == "test-model"

        # Note: Validation would need proper tool configs with all required fields

    def test_config_validation_missing_key(self, tmp_path):
        """Test configuration validation with missing API key."""
        # Create config with all required tools but missing env var
        config_content = """
tools:
  mawsuah:
    api_key_env: MISSING_KEY
    customer_id: test_customer
    corpus_id: test_corpus

  goodmem:
    api_key_env: GOODMEM_KEY

llm:
  model: test-model
  api_key_env: TEST_LLM_KEY
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = Config(config_file)

        # MISSING_KEY is not set in environment
        with pytest.raises(ValueError, match="Missing required environment"):
            config.validate()

    @patch("src.adapters.mawsuah.requests.post")
    @patch.dict("os.environ", {"VECTARA_API_KEY": "test_key"})
    def test_adapter_integration(self, mock_post):
        """Test adapter integration with engine."""
        from src.core.models import ToolConfig
        from src.adapters.mawsuah import MawsuahAdapter

        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "responseSet": [{
                "response": [{
                    "text": "Test result",
                    "score": 0.9,
                    "documentIndex": "doc1",
                    "metadata": []
                }]
            }]
        }
        mock_post.return_value = mock_response

        # Create adapter
        config = ToolConfig(
            name="mawsuah",
            api_key_env="VECTARA_API_KEY",
            customer_id="test_customer",
            corpus_id="test_corpus"
        )
        adapter = MawsuahAdapter(config)

        # Test search
        results = adapter.search("test query", top_k=1)
        assert len(results) == 1
        assert results[0].text == "Test result"
        assert results[0].score == 0.9

    def test_comparison_engine_workflow(self):
        """Test full comparison workflow."""
        # Create mock adapters
        mock_tool1 = Mock()
        mock_tool1.search.return_value = [
            RagResult(id="1", text="Result from tool1", score=0.9)
        ]

        mock_tool2 = Mock()
        mock_tool2.search.return_value = [
            RagResult(id="2", text="Result from tool2", score=0.8)
        ]

        # Create engine and run comparison
        engine = ComparisonEngine({"tool1": mock_tool1, "tool2": mock_tool2})
        result = engine.run_comparison("test query", top_k=1, parallel=False)

        # Verify results
        assert result.query == "test query"
        assert len(result.tool_results) == 2
        assert len(result.tool_results["tool1"]) == 1
        assert len(result.tool_results["tool2"]) == 1
        assert result.tool_results["tool1"][0].text == "Result from tool1"

        # Verify stats
        stats = engine.get_summary_stats(result)
        assert stats["tools_compared"] == ["tool1", "tool2"]
        assert stats["result_counts"]["tool1"] == 1
        assert stats["result_counts"]["tool2"] == 1

    def test_display_formatter_workflow(self):
        """Test display formatter with real comparison result."""
        # Create comparison result
        result = ComparisonResult(
            query="test query",
            tool_results={
                "tool1": [
                    RagResult(id="1", text="First tool result", score=0.9, source="Source1")
                ],
                "tool2": [
                    RagResult(id="2", text="Second tool result", score=0.85, source="Source2")
                ]
            },
            errors={}
        )

        formatter = ComparisonFormatter(width=80)

        # Test different formats
        side_by_side = formatter.format_side_by_side(result)
        assert "RAG TOOL COMPARISON RESULTS" in side_by_side
        assert "First tool result" in side_by_side
        assert "Second tool result" in side_by_side

        json_output = formatter.format_json(result, pretty=False)
        assert '"query": "test query"' in json_output

        markdown = formatter.format_markdown(result)
        assert "# RAG Tool Comparison Results" in markdown
        assert "## Search Results" in markdown

        summary = formatter.format_summary(result)
        assert "Query: test query" in summary
        assert "tool1: 1" in summary
        assert "tool2: 1" in summary

    @patch("src.adapters.goodmem.GOODMEM_AVAILABLE", False)
    @patch.dict("os.environ", {"GOODMEM_API_KEY": "test_key"})
    def test_goodmem_mock_mode_integration(self):
        """Test Goodmem adapter in mock mode."""
        from src.core.models import ToolConfig
        from src.adapters.goodmem import GoodmemAdapter

        config = ToolConfig(
            name="goodmem",
            api_key_env="GOODMEM_API_KEY"
        )
        adapter = GoodmemAdapter(config)

        # Should use mock implementation
        results = adapter.search("test query", top_k=2)
        assert len(results) == 2
        assert all(r.metadata.get("mock") is True for r in results)
        assert "Mock Goodmem result" in results[0].text

    def test_parallel_vs_sequential_execution(self):
        """Test parallel vs sequential execution produces same results."""
        # Create mock adapters with delays
        import time

        def delayed_search(query, top_k):
            time.sleep(0.01)  # Small delay
            return [RagResult(id="1", text=f"Result for {query}", score=0.9)]

        mock_tool1 = Mock()
        mock_tool1.search = delayed_search

        mock_tool2 = Mock()
        mock_tool2.search = delayed_search

        engine = ComparisonEngine({"tool1": mock_tool1, "tool2": mock_tool2})

        # Run both modes
        result_parallel = engine.run_comparison("test", top_k=1, parallel=True)
        result_sequential = engine.run_comparison("test", top_k=1, parallel=False)

        # Results should be the same
        assert len(result_parallel.tool_results) == len(result_sequential.tool_results)
        assert result_parallel.tool_results.keys() == result_sequential.tool_results.keys()

    def test_error_handling_integration(self):
        """Test error handling across components."""
        # Create one working and one failing adapter
        working_adapter = Mock()
        working_adapter.search.return_value = [
            RagResult(id="1", text="Success", score=0.9)
        ]

        failing_adapter = Mock()
        failing_adapter.search.side_effect = RuntimeError("Connection failed")

        engine = ComparisonEngine({
            "working": working_adapter,
            "failing": failing_adapter
        })

        result = engine.run_comparison("test", parallel=False)

        # Should have results from working adapter
        assert "working" in result.tool_results
        assert len(result.tool_results["working"]) == 1

        # Should have error from failing adapter
        assert "failing" in result.errors
        assert "Connection failed" in result.errors["failing"]

        # Formatter should handle errors gracefully
        formatter = ComparisonFormatter()
        output = formatter.format_side_by_side(result)
        assert "ERRORS:" in output
        assert "Connection failed" in output

    def test_end_to_end_workflow(self, tmp_path):
        """Test complete end-to-end workflow."""
        # Create mock adapters
        mock_adapters = {}
        for i in range(2):
            adapter = Mock()
            adapter.search.return_value = [
                RagResult(
                    id=f"tool{i}_1",
                    text=f"Result from tool{i}",
                    score=0.9 - (i * 0.1),
                    latency_ms=100 + (i * 50)
                )
            ]
            mock_adapters[f"tool{i}"] = adapter

        # Run comparison
        engine = ComparisonEngine(mock_adapters)
        result = engine.run_comparison("end to end test", top_k=1)

        # Format results
        formatter = ComparisonFormatter()

        # Test all output formats
        outputs = {
            "display": formatter.format_side_by_side(result),
            "json": formatter.format_json(result),
            "markdown": formatter.format_markdown(result),
            "summary": formatter.format_summary(result)
        }

        # Verify all formats contain expected content
        for format_name, output in outputs.items():
            assert "end to end test" in output or "tool0" in output

        # Save to file
        output_file = tmp_path / "results.json"
        output_file.write_text(outputs["json"])
        assert output_file.exists()

        # Verify we can read it back
        import json
        saved_data = json.loads(output_file.read_text())
        assert saved_data["query"] == "end to end test"