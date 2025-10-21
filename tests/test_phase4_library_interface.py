"""Tests for Phase 4: Top-Level Library Interface.

Tests the public API exported from the ragdiff package.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

import ragdiff
from ragdiff import (
    compare,
    evaluate_with_llm,
    get_available_adapters,
    load_config,
    query,
    run_batch,
    validate_config,
)
from ragdiff.core.models import ComparisonResult, RagResult


class TestPublicAPIExports:
    """Test that all public API functions are exported correctly."""

    def test_version_exported(self):
        """Test that __version__ is exported."""
        assert hasattr(ragdiff, "__version__")
        assert isinstance(ragdiff.__version__, str)
        assert ragdiff.__version__ == "1.0.0"

    def test_adapter_api_version_exported(self):
        """Test that ADAPTER_API_VERSION is exported."""
        assert hasattr(ragdiff, "ADAPTER_API_VERSION")
        assert ragdiff.ADAPTER_API_VERSION == "1.0.0"

    def test_core_functions_exported(self):
        """Test that core API functions are exported."""
        assert callable(ragdiff.query)
        assert callable(ragdiff.run_batch)
        assert callable(ragdiff.compare)
        assert callable(ragdiff.evaluate_with_llm)

    def test_config_functions_exported(self):
        """Test that configuration functions are exported."""
        assert callable(ragdiff.load_config)
        assert callable(ragdiff.validate_config)
        assert callable(ragdiff.get_available_adapters)

    def test_models_exported(self):
        """Test that data models are exported."""
        assert hasattr(ragdiff, "RagResult")
        assert hasattr(ragdiff, "ComparisonResult")
        assert hasattr(ragdiff, "LLMEvaluation")

    def test_errors_exported(self):
        """Test that error classes are exported."""
        assert hasattr(ragdiff, "RagDiffError")
        assert hasattr(ragdiff, "ConfigurationError")
        assert hasattr(ragdiff, "AdapterError")
        assert hasattr(ragdiff, "AdapterRegistryError")
        assert hasattr(ragdiff, "ValidationError")
        assert hasattr(ragdiff, "EvaluationError")

    def test_all_contains_expected_exports(self):
        """Test that __all__ contains all expected exports."""
        expected = {
            "__version__",
            "ADAPTER_API_VERSION",
            "query",
            "run_batch",
            "compare",
            "evaluate_with_llm",
            "load_config",
            "validate_config",
            "get_available_adapters",
            "RagResult",
            "ComparisonResult",
            "LLMEvaluation",
            "RagDiffError",
            "ConfigurationError",
            "AdapterError",
            "AdapterRegistryError",
            "ValidationError",
            "EvaluationError",
        }
        assert set(ragdiff.__all__) == expected


class TestQueryFunction:
    """Test the query() function."""

    @patch("ragdiff.api.create_adapter")
    @patch("ragdiff.api.Config")
    def test_query_success(self, mock_config_class, mock_create_adapter):
        """Test successful single query."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock()}
        mock_config_class.return_value = mock_config

        mock_adapter = MagicMock()
        mock_results = [
            RagResult(id="1", text="Result 1", score=0.9, source="Test"),
            RagResult(id="2", text="Result 2", score=0.8, source="Test"),
        ]
        mock_adapter.search.return_value = mock_results
        mock_create_adapter.return_value = mock_adapter

        # Call function
        results = query("config.yaml", "test query", tool="vectara", top_k=2)

        # Verify
        assert len(results) == 2
        assert results[0].text == "Result 1"
        assert results[1].text == "Result 2"
        mock_adapter.search.assert_called_once_with("test query", top_k=2)

    @patch("ragdiff.api.Config")
    def test_query_tool_not_found(self, mock_config_class):
        """Test query with non-existent tool."""
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock()}
        mock_config_class.return_value = mock_config

        with pytest.raises(
            ragdiff.ConfigurationError, match="Tool 'nonexistent' not found"
        ):
            query("config.yaml", "test query", tool="nonexistent")


class TestRunBatchFunction:
    """Test the run_batch() function."""

    @patch("ragdiff.api.ComparisonEngine")
    @patch("ragdiff.api.create_adapter")
    @patch("ragdiff.api.Config")
    def test_run_batch_success(
        self, mock_config_class, mock_create_adapter, mock_engine_class
    ):
        """Test successful batch query execution."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock(), "goodmem": MagicMock()}
        mock_config.get_llm_config.return_value = None
        mock_config_class.return_value = mock_config

        mock_adapter = MagicMock()
        mock_create_adapter.return_value = mock_adapter

        mock_engine = MagicMock()
        mock_result1 = MagicMock(spec=ComparisonResult)
        mock_result2 = MagicMock(spec=ComparisonResult)
        mock_engine.run_comparison.side_effect = [mock_result1, mock_result2]
        mock_engine_class.return_value = mock_engine

        # Call function
        queries = ["query1", "query2"]
        results = run_batch(
            "config.yaml",
            queries,
            tools=["vectara", "goodmem"],
            top_k=5,
            parallel=True,
            evaluate=False,
        )

        # Verify
        assert len(results) == 2
        assert mock_engine.run_comparison.call_count == 2

    @patch("ragdiff.api.Config")
    def test_run_batch_tool_not_found(self, mock_config_class):
        """Test run_batch with non-existent tool."""
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock()}
        mock_config_class.return_value = mock_config

        with pytest.raises(
            ragdiff.ConfigurationError, match="Tool 'nonexistent' not found"
        ):
            run_batch("config.yaml", ["query1"], tools=["nonexistent"])


class TestCompareFunction:
    """Test the compare() function."""

    @patch("ragdiff.api.ComparisonEngine")
    @patch("ragdiff.api.create_adapter")
    @patch("ragdiff.api.Config")
    def test_compare_success(
        self, mock_config_class, mock_create_adapter, mock_engine_class
    ):
        """Test successful comparison."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock(), "goodmem": MagicMock()}
        mock_config.get_llm_config.return_value = None
        mock_config_class.return_value = mock_config

        mock_adapter = MagicMock()
        mock_create_adapter.return_value = mock_adapter

        mock_engine = MagicMock()
        mock_result = MagicMock(spec=ComparisonResult)
        mock_engine.run_comparison.return_value = mock_result
        mock_engine_class.return_value = mock_engine

        # Call function
        result = compare(
            "config.yaml",
            "test query",
            tools=["vectara", "goodmem"],
            top_k=5,
            parallel=True,
            evaluate=False,
        )

        # Verify
        assert result == mock_result
        mock_engine.run_comparison.assert_called_once_with(
            "test query", top_k=5, parallel=True
        )

    @patch("ragdiff.api.Config")
    def test_compare_all_tools_default(self, mock_config_class):
        """Test compare uses all configured tools by default."""
        with patch("ragdiff.api.create_adapter") as mock_create_adapter:
            with patch("ragdiff.api.ComparisonEngine") as mock_engine_class:
                mock_config = MagicMock()
                mock_config.tools = {
                    "vectara": MagicMock(),
                    "goodmem": MagicMock(),
                    "agentset": MagicMock(),
                }
                mock_config.get_llm_config.return_value = None
                mock_config_class.return_value = mock_config

                mock_adapter = MagicMock()
                mock_create_adapter.return_value = mock_adapter

                mock_engine = MagicMock()
                mock_result = MagicMock(spec=ComparisonResult)
                mock_engine.run_comparison.return_value = mock_result
                mock_engine_class.return_value = mock_engine

                # Call without specifying tools
                compare("config.yaml", "test query")

                # Verify all 3 adapters were created
                assert mock_create_adapter.call_count == 3


class TestEvaluateWithLLM:
    """Test the evaluate_with_llm() function."""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ragdiff.api.LLMEvaluator")
    def test_evaluate_success(self, mock_evaluator_class):
        """Test successful LLM evaluation."""
        # Setup mocks
        mock_evaluation = MagicMock()
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = mock_evaluation
        mock_evaluator_class.return_value = mock_evaluator

        mock_result = MagicMock(spec=ComparisonResult)

        # Call function
        result = evaluate_with_llm(mock_result)

        # Verify
        assert result == mock_result
        assert mock_result.llm_evaluation == mock_evaluation
        mock_evaluator_class.assert_called_once_with(
            model="claude-sonnet-4-20250514", api_key="test-key"
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_evaluate_missing_api_key(self):
        """Test evaluate_with_llm fails without API key."""
        mock_result = MagicMock(spec=ComparisonResult)

        with pytest.raises(
            ragdiff.ConfigurationError,
            match="ANTHROPIC_API_KEY environment variable not set",
        ):
            evaluate_with_llm(mock_result)


class TestGetAvailableAdapters:
    """Test the get_available_adapters() function."""

    def test_get_available_adapters_returns_list(self):
        """Test that get_available_adapters returns a list."""
        adapters = get_available_adapters()
        assert isinstance(adapters, list)
        assert len(adapters) > 0

    def test_adapter_metadata_structure(self):
        """Test that each adapter has required metadata fields."""
        adapters = get_available_adapters()

        for adapter in adapters:
            assert "name" in adapter
            assert "api_version" in adapter
            assert "required_env_vars" in adapter
            assert "options_schema" in adapter
            assert isinstance(adapter["name"], str)
            assert isinstance(adapter["api_version"], str)
            assert isinstance(adapter["required_env_vars"], list)
            assert isinstance(adapter["options_schema"], dict)

    def test_known_adapters_present(self):
        """Test that known adapters are in the list."""
        adapters = get_available_adapters()
        adapter_names = [a["name"] for a in adapters]

        assert "vectara" in adapter_names
        assert "goodmem" in adapter_names
        assert "agentset" in adapter_names


class TestLoadConfig:
    """Test the load_config() function."""

    @patch("ragdiff.api.Config")
    def test_load_config_success(self, mock_config_class):
        """Test successful config loading."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        result = load_config("config.yaml")

        assert result == mock_config
        mock_config.validate.assert_called_once()

    @patch("ragdiff.api.Config")
    def test_load_config_validates(self, mock_config_class):
        """Test that load_config calls validate()."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        load_config("config.yaml")

        mock_config.validate.assert_called_once()


class TestValidateConfig:
    """Test the validate_config() function."""

    @patch("ragdiff.api.Config")
    def test_validate_config_valid(self, mock_config_class):
        """Test validation of valid config."""
        mock_config = MagicMock()
        mock_config.tools = {"vectara": MagicMock(), "goodmem": MagicMock()}
        mock_config.get_llm_config.return_value = {"model": "claude"}
        mock_config_class.return_value = mock_config

        result = validate_config("config.yaml")

        assert result["valid"] is True
        assert result["errors"] == []
        assert "vectara" in result["tools"]
        assert "goodmem" in result["tools"]
        assert result["llm_configured"] is True

    @patch("ragdiff.api.Config")
    def test_validate_config_invalid(self, mock_config_class):
        """Test validation of invalid config."""
        mock_config_class.side_effect = ValueError("Invalid config")

        result = validate_config("config.yaml")

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "Invalid config" in result["errors"][0]
        assert result["tools"] == []


class TestImportPatterns:
    """Test that import patterns work as documented."""

    def test_top_level_import(self):
        """Test importing from top level."""
        from ragdiff import compare, query, run_batch

        assert callable(query)
        assert callable(run_batch)
        assert callable(compare)

    def test_star_import(self):
        """Test that star import only includes __all__."""
        # This test verifies that only exported items are in __all__
        import ragdiff

        exported = set(ragdiff.__all__)

        # Verify no private items
        for item in exported:
            assert not item.startswith("_") or item in ("__version__",)

    def test_model_import(self):
        """Test importing models."""
        from ragdiff import ComparisonResult, LLMEvaluation, RagResult

        assert RagResult is not None
        assert ComparisonResult is not None
        assert LLMEvaluation is not None

    def test_error_import(self):
        """Test importing errors."""
        from ragdiff import AdapterError, ConfigurationError

        assert issubclass(ConfigurationError, Exception)
        assert issubclass(AdapterError, Exception)
