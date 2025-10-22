"""Tests for API functions with multi-tenant support."""

import pytest

from ragdiff import compare, load_config, query, run_batch
from ragdiff.core.errors import ConfigurationError
from ragdiff.core.models import ComparisonResult, RagResult


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary."""
    return {
        "tools": {
            "vectara": {
                "api_key_env": "VECTARA_API_KEY",
                "corpus_id": "test_corpus",
                "base_url": "https://api.vectara.io",
            }
        }
    }


@pytest.fixture
def mock_credentials():
    """Mock tenant credentials."""
    return {"VECTARA_API_KEY": "test_tenant_key_123"}


class TestQueryWithConfig:
    """Test query() function with Config objects."""

    def test_query_accepts_config_object(
        self, sample_config_dict, mock_credentials, monkeypatch
    ):
        """Test query accepts Config object."""

        # Mock the adapter's search method
        def mock_search(self, query_text, top_k=5):
            return [
                RagResult(
                    id="1",
                    text="Result 1",
                    score=0.9,
                    source="vectara",
                    metadata={},
                )
            ]

        from ragdiff.adapters import vectara

        monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)

        # Load config with credentials
        config = load_config(sample_config_dict, credentials=mock_credentials)

        # Query with Config object
        results = query(config, "test query", tool="vectara", top_k=5)

        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], RagResult)

    def test_query_backward_compatible_with_path(self, tmp_path, monkeypatch):
        """Test query still works with file path (backward compat)."""
        import os

        # Set environment variable
        os.environ["TEST_VECTARA_KEY"] = "env_key"

        try:
            # Create config file
            config_file = tmp_path / "config.yaml"
            config_file.write_text(
                """
tools:
  vectara:
    api_key_env: TEST_VECTARA_KEY
    corpus_id: test_corpus
"""
            )

            # Mock search
            def mock_search(self, query_text, top_k=5):
                return [
                    RagResult(
                        id="1", text="Result", score=0.9, source="vectara", metadata={}
                    )
                ]

            from ragdiff.adapters import vectara

            monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)

            # Old usage - pass file path
            results = query(str(config_file), "test query", tool="vectara")

            assert isinstance(results, list)
            assert len(results) > 0
        finally:
            del os.environ["TEST_VECTARA_KEY"]


class TestCompareWithConfig:
    """Test compare() function with Config objects."""

    def test_compare_accepts_config_object(
        self, sample_config_dict, mock_credentials, monkeypatch
    ):
        """Test compare accepts Config object."""

        # Mock search
        def mock_search(self, query_text, top_k=5):
            return [
                RagResult(
                    id="1",
                    text="Result 1",
                    score=0.9,
                    source=self.name,
                    metadata={},
                )
            ]

        from ragdiff.adapters import vectara

        monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)

        # Load config
        config = load_config(sample_config_dict, credentials=mock_credentials)

        # Compare with Config object
        result = compare(config, "test query", tools=["vectara"], top_k=5)

        assert isinstance(result, ComparisonResult)
        assert "vectara" in result.tool_results

    def test_compare_with_multiple_tools(self, mock_credentials, monkeypatch):
        """Test compare with multiple tools."""
        config_dict = {
            "tools": {
                "vectara": {
                    "api_key_env": "VECTARA_API_KEY",
                    "corpus_id": "test",
                },
                "goodmem": {
                    "api_key_env": "GOODMEM_API_KEY",
                    "base_url": "http://test",
                },
            }
        }

        # Mock search for both adapters
        def mock_search(self, query_text, top_k=5):
            return [
                RagResult(
                    id="1",
                    text=f"Result from {self.name}",
                    score=0.9,
                    source=self.name,
                    metadata={},
                )
            ]

        from ragdiff.adapters import goodmem, vectara

        monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)
        monkeypatch.setattr(goodmem.GoodmemAdapter, "search", mock_search)

        credentials = {
            "VECTARA_API_KEY": "vectara_key",
            "GOODMEM_API_KEY": "goodmem_key",
        }

        config = load_config(config_dict, credentials=credentials)

        result = compare(config, "test query", tools=["vectara", "goodmem"])

        assert "vectara" in result.tool_results
        assert "goodmem" in result.tool_results


class TestRunBatchWithConfig:
    """Test run_batch() function with Config objects."""

    def test_run_batch_accepts_config_object(
        self, sample_config_dict, mock_credentials, monkeypatch
    ):
        """Test run_batch accepts Config object."""

        # Mock search
        def mock_search(self, query_text, top_k=5):
            return [
                RagResult(
                    id="1",
                    text=f"Result for {query_text}",
                    score=0.9,
                    source="vectara",
                    metadata={},
                )
            ]

        from ragdiff.adapters import vectara

        monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)

        config = load_config(sample_config_dict, credentials=mock_credentials)

        queries = ["query 1", "query 2"]
        results = run_batch(config, queries, tools=["vectara"])

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, ComparisonResult) for r in results)


class TestMultiTenantAPIUsage:
    """Test multi-tenant API usage patterns."""

    def test_different_tenants_isolated(self, sample_config_dict, monkeypatch):
        """Test different tenant configs are isolated."""

        # Mock search
        def mock_search(self, query_text, top_k=5):
            # Return API key in result to verify isolation
            return [
                RagResult(
                    id="1",
                    text=f"Key: {self.api_key}",
                    score=0.9,
                    source="vectara",
                    metadata={},
                )
            ]

        from ragdiff.adapters import vectara

        monkeypatch.setattr(vectara.VectaraAdapter, "search", mock_search)

        # Tenant A
        config_a = load_config(
            sample_config_dict, credentials={"VECTARA_API_KEY": "tenant_a_key"}
        )
        results_a = query(config_a, "test", tool="vectara")

        # Tenant B
        config_b = load_config(
            sample_config_dict, credentials={"VECTARA_API_KEY": "tenant_b_key"}
        )
        results_b = query(config_b, "test", tool="vectara")

        # Results should contain different keys
        assert "tenant_a_key" in results_a[0].text
        assert "tenant_b_key" in results_b[0].text


class TestAdapterCredentialPassing:
    """Test adapters receive credentials correctly."""

    def test_adapter_receives_credentials_from_config(
        self, sample_config_dict, mock_credentials
    ):
        """Test adapter receives credentials from Config."""
        config = load_config(sample_config_dict, credentials=mock_credentials)

        # Create adapter via factory
        from ragdiff.adapters.factory import create_adapter

        adapter = create_adapter(
            "vectara",
            config.tools["vectara"],
            credentials=config._credentials,
        )

        # Adapter should have the credential
        assert adapter.api_key == "test_tenant_key_123"

    def test_adapter_without_credentials_fails(self, sample_config_dict):
        """Test adapter fails when credentials missing."""
        config_dict = {
            "tools": {
                "vectara": {
                    "api_key_env": "NONEXISTENT_KEY",
                    "corpus_id": "test",
                }
            }
        }

        config = load_config(config_dict)

        from ragdiff.adapters.factory import create_adapter

        with pytest.raises(ConfigurationError, match="Missing API key"):
            create_adapter(
                "vectara", config.tools["vectara"], credentials=config._credentials
            )
