"""Tests for Phase 2: Adapter Migration.

Tests the migration of adapters to the new RagAdapter ABC and registry system.
"""

import os
from unittest.mock import patch

import pytest

from ragdiff.adapters import get_adapter, list_available_adapters
from ragdiff.adapters.abc import RagAdapter
from ragdiff.adapters.agentset import AgentsetAdapter
from ragdiff.adapters.goodmem import GoodmemAdapter
from ragdiff.adapters.vectara import VectaraAdapter
from ragdiff.core.errors import ConfigurationError
from ragdiff.core.models import ToolConfig


class TestAdapterRegistration:
    """Test that all adapters are properly registered."""

    def test_all_adapters_registered(self):
        """Verify all three adapters are auto-registered."""
        available = list_available_adapters()
        assert "vectara" in available
        assert "goodmem" in available
        assert "agentset" in available

    def test_get_vectara_adapter(self):
        """Verify Vectara adapter can be retrieved from registry."""
        adapter_class = get_adapter("vectara")
        assert adapter_class is not None
        assert adapter_class == VectaraAdapter

    def test_get_goodmem_adapter(self):
        """Verify Goodmem adapter can be retrieved from registry."""
        adapter_class = get_adapter("goodmem")
        assert adapter_class is not None
        assert adapter_class == GoodmemAdapter

    def test_get_agentset_adapter(self):
        """Verify Agentset adapter can be retrieved from registry."""
        adapter_class = get_adapter("agentset")
        assert adapter_class is not None
        assert adapter_class == AgentsetAdapter


class TestAdapterInheritance:
    """Test that all adapters properly inherit from RagAdapter."""

    def test_vectara_inherits_from_rag_adapter(self):
        """Verify VectaraAdapter inherits from RagAdapter."""
        assert issubclass(VectaraAdapter, RagAdapter)

    def test_goodmem_inherits_from_rag_adapter(self):
        """Verify GoodmemAdapter inherits from RagAdapter."""
        assert issubclass(GoodmemAdapter, RagAdapter)

    def test_agentset_inherits_from_rag_adapter(self):
        """Verify AgentsetAdapter inherits from RagAdapter."""
        assert issubclass(AgentsetAdapter, RagAdapter)


class TestAdapterMetadata:
    """Test adapter metadata (API version, name, schema)."""

    def test_vectara_metadata(self):
        """Verify Vectara adapter has correct metadata."""
        assert VectaraAdapter.ADAPTER_API_VERSION == "1.0.0"
        assert VectaraAdapter.ADAPTER_NAME == "vectara"

    def test_goodmem_metadata(self):
        """Verify Goodmem adapter has correct metadata."""
        assert GoodmemAdapter.ADAPTER_API_VERSION == "1.0.0"
        assert GoodmemAdapter.ADAPTER_NAME == "goodmem"

    def test_agentset_metadata(self):
        """Verify Agentset adapter has correct metadata."""
        assert AgentsetAdapter.ADAPTER_API_VERSION == "1.0.0"
        assert AgentsetAdapter.ADAPTER_NAME == "agentset"


class TestVectaraAdapter:
    """Test VectaraAdapter implementation."""

    def test_validate_config_missing_api_key_env(self):
        """Test validation fails when api_key_env is missing."""
        config = {"corpus_id": "test-corpus"}
        with pytest.raises(
            ConfigurationError, match="missing required field: api_key_env"
        ):
            VectaraAdapter.validate_config(VectaraAdapter, config)

    def test_validate_config_missing_corpus_id(self):
        """Test validation fails when corpus_id is missing."""
        config = {"api_key_env": "VECTARA_API_KEY"}
        with pytest.raises(
            ConfigurationError, match="missing required field: corpus_id"
        ):
            VectaraAdapter.validate_config(VectaraAdapter, config)

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_config_env_var_not_set(self):
        """Test validation fails when env var is not set."""
        config = {"api_key_env": "VECTARA_API_KEY", "corpus_id": "test-corpus"}
        with pytest.raises(
            ConfigurationError, match="Environment variable VECTARA_API_KEY is not set"
        ):
            VectaraAdapter.validate_config(VectaraAdapter, config)

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test-key"})
    def test_validate_config_success(self):
        """Test validation succeeds with valid config."""
        config = ToolConfig(
            name="vectara-test",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test-corpus",
        )
        # Should not raise
        adapter = VectaraAdapter(config)
        assert adapter.corpus_id == "test-corpus"

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test-key"})
    def test_get_required_env_vars(self):
        """Test get_required_env_vars returns correct list."""
        config = ToolConfig(
            name="vectara-test",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test-corpus",
        )
        adapter = VectaraAdapter(config)
        env_vars = adapter.get_required_env_vars()
        assert env_vars == ["VECTARA_API_KEY"]

    def test_get_options_schema(self):
        """Test get_options_schema returns valid JSON schema."""
        schema = VectaraAdapter.get_options_schema(VectaraAdapter)
        assert schema["type"] == "object"
        assert "corpus_id" in schema["properties"]
        assert "base_url" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "default_top_k" in schema["properties"]
        assert "corpus_id" in schema["required"]


class TestGoodmemAdapter:
    """Test GoodmemAdapter implementation."""

    def test_validate_config_missing_api_key_env(self):
        """Test validation fails when api_key_env is missing."""
        config = {}
        with pytest.raises(
            ConfigurationError, match="missing required field: api_key_env"
        ):
            GoodmemAdapter.validate_config(GoodmemAdapter, config)

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_config_env_var_not_set(self):
        """Test validation fails when env var is not set."""
        config = {"api_key_env": "GOODMEM_API_KEY"}
        with pytest.raises(
            ConfigurationError, match="Environment variable GOODMEM_API_KEY is not set"
        ):
            GoodmemAdapter.validate_config(GoodmemAdapter, config)

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test-key"})
    def test_validate_config_success(self):
        """Test validation succeeds with valid config."""
        config = ToolConfig(
            name="goodmem-test",
            api_key_env="GOODMEM_API_KEY",
        )
        # Should not raise
        adapter = GoodmemAdapter(config)
        assert adapter.api_key == "test-key"

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test-key"})
    def test_get_required_env_vars(self):
        """Test get_required_env_vars returns correct list."""
        config = ToolConfig(
            name="goodmem-test",
            api_key_env="GOODMEM_API_KEY",
        )
        adapter = GoodmemAdapter(config)
        env_vars = adapter.get_required_env_vars()
        assert env_vars == ["GOODMEM_API_KEY"]

    def test_get_options_schema(self):
        """Test get_options_schema returns valid JSON schema."""
        schema = GoodmemAdapter.get_options_schema(GoodmemAdapter)
        assert schema["type"] == "object"
        assert "space_ids" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "default_top_k" in schema["properties"]


class TestAgentsetAdapter:
    """Test AgentsetAdapter implementation."""

    def test_validate_config_missing_api_key_env(self):
        """Test validation fails when api_key_env is missing."""
        config = {}
        with pytest.raises(
            ConfigurationError, match="missing required field: api_key_env"
        ):
            AgentsetAdapter.validate_config(AgentsetAdapter, config)

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_config_env_var_not_set(self):
        """Test validation fails when env var is not set."""
        config = {"api_key_env": "AGENTSET_API_KEY"}
        with pytest.raises(
            ConfigurationError, match="Environment variable AGENTSET_API_KEY is not set"
        ):
            AgentsetAdapter.validate_config(AgentsetAdapter, config)

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_validate_config_success(self):
        """Test validation succeeds with valid config."""
        config = ToolConfig(
            name="agentset-test",
            api_key_env="AGENTSET_API_KEY",
        )
        # Mock the Agentset client to avoid actual initialization
        with patch("ragdiff.adapters.agentset.Agentset"):
            adapter = AgentsetAdapter(config)
            assert adapter.api_key == "test-key"
            assert adapter.namespace_id == "test-ns"

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_get_required_env_vars(self):
        """Test get_required_env_vars returns correct list."""
        config = ToolConfig(
            name="agentset-test",
            api_key_env="AGENTSET_API_KEY",
        )
        with patch("ragdiff.adapters.agentset.Agentset"):
            adapter = AgentsetAdapter(config)
            env_vars = adapter.get_required_env_vars()
            assert "AGENTSET_API_KEY" in env_vars
            assert "AGENTSET_NAMESPACE_ID" in env_vars

    def test_get_options_schema(self):
        """Test get_options_schema returns valid JSON schema."""
        schema = AgentsetAdapter.get_options_schema(AgentsetAdapter)
        assert schema["type"] == "object"
        assert "namespace_id_env" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "default_top_k" in schema["properties"]
        assert "rerank" in schema["properties"]

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_rerank_option_default_true(self):
        """Test rerank option defaults to True."""
        config = ToolConfig(
            name="agentset-test",
            api_key_env="AGENTSET_API_KEY",
        )
        with patch("ragdiff.adapters.agentset.Agentset"):
            adapter = AgentsetAdapter(config)
            assert adapter.rerank is True

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_rerank_option_can_be_disabled(self):
        """Test rerank option can be disabled via config."""
        config = ToolConfig(
            name="agentset-test",
            api_key_env="AGENTSET_API_KEY",
            options={"rerank": False},
        )
        with patch("ragdiff.adapters.agentset.Agentset"):
            adapter = AgentsetAdapter(config)
            assert adapter.rerank is False


class TestFactoryWithRegistry:
    """Test factory integration with registry."""

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test-key"})
    def test_create_vectara_adapter(self):
        """Test factory creates Vectara adapter using registry."""
        from ragdiff.adapters.factory import create_adapter

        config = ToolConfig(
            name="vectara-test",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test-corpus",
        )
        adapter = create_adapter("vectara", config)
        assert isinstance(adapter, VectaraAdapter)
        assert isinstance(adapter, RagAdapter)

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test-key"})
    def test_create_goodmem_adapter(self):
        """Test factory creates Goodmem adapter using registry."""
        from ragdiff.adapters.factory import create_adapter

        config = ToolConfig(
            name="goodmem-test",
            api_key_env="GOODMEM_API_KEY",
        )
        adapter = create_adapter("goodmem", config)
        assert isinstance(adapter, GoodmemAdapter)
        assert isinstance(adapter, RagAdapter)

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_create_agentset_adapter(self):
        """Test factory creates Agentset adapter using registry."""
        from ragdiff.adapters.factory import create_adapter

        with patch("ragdiff.adapters.agentset.Agentset"):
            config = ToolConfig(
                name="agentset-test",
                api_key_env="AGENTSET_API_KEY",
            )
            adapter = create_adapter("agentset", config)
            assert isinstance(adapter, AgentsetAdapter)
            assert isinstance(adapter, RagAdapter)

    def test_create_unknown_adapter_raises_error(self):
        """Test factory raises AdapterRegistryError for unknown adapter."""
        from ragdiff.adapters.factory import create_adapter
        from ragdiff.core.errors import AdapterRegistryError

        config = ToolConfig(
            name="unknown-adapter",
            api_key_env="UNKNOWN_API_KEY",
        )
        with pytest.raises(
            AdapterRegistryError, match="Unknown adapter: unknown-adapter"
        ):
            create_adapter("unknown-adapter", config)

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test-key"})
    def test_create_adapter_with_variant_name(self):
        """Test factory uses config.adapter field for variants."""
        from ragdiff.adapters.factory import create_adapter

        config = ToolConfig(
            name="vectara-tafsir",
            adapter="vectara",  # Variant uses base adapter
            api_key_env="VECTARA_API_KEY",
            corpus_id="tafsir-corpus",
        )
        adapter = create_adapter("vectara-tafsir", config)
        assert isinstance(adapter, VectaraAdapter)
        assert adapter.corpus_id == "tafsir-corpus"


class TestBackwardCompatibility:
    """Test that existing functionality still works."""

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test-key"})
    def test_vectara_search_interface_unchanged(self):
        """Test Vectara search method signature is unchanged."""
        config = ToolConfig(
            name="vectara-test",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test-corpus",
        )
        adapter = VectaraAdapter(config)

        # Verify method exists and has correct signature
        assert hasattr(adapter, "search")
        assert callable(adapter.search)

        # Method should accept query and top_k
        import inspect

        sig = inspect.signature(adapter.search)
        assert "query" in sig.parameters
        assert "top_k" in sig.parameters

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test-key"})
    def test_goodmem_search_interface_unchanged(self):
        """Test Goodmem search method signature is unchanged."""
        config = ToolConfig(
            name="goodmem-test",
            api_key_env="GOODMEM_API_KEY",
        )
        adapter = GoodmemAdapter(config)

        assert hasattr(adapter, "search")
        assert callable(adapter.search)

        import inspect

        sig = inspect.signature(adapter.search)
        assert "query" in sig.parameters
        assert "top_k" in sig.parameters

    @patch.dict(
        os.environ, {"AGENTSET_API_KEY": "test-key", "AGENTSET_NAMESPACE_ID": "test-ns"}
    )
    def test_agentset_search_interface_unchanged(self):
        """Test Agentset search method signature is unchanged."""
        config = ToolConfig(
            name="agentset-test",
            api_key_env="AGENTSET_API_KEY",
        )
        with patch("ragdiff.adapters.agentset.Agentset"):
            adapter = AgentsetAdapter(config)

            assert hasattr(adapter, "search")
            assert callable(adapter.search)

            import inspect

            sig = inspect.signature(adapter.search)
            assert "query" in sig.parameters
            assert "top_k" in sig.parameters
