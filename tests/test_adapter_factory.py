"""Tests for adapter factory.

NOTE: Comprehensive adapter migration tests are in test_phase2_adapter_migration.py.
This file retains backward compatibility tests for the factory's variant functionality.
"""

import os
from unittest.mock import patch

import pytest

from ragdiff.adapters.factory import create_adapter, get_available_adapters
from ragdiff.core.errors import AdapterRegistryError
from ragdiff.core.models import ToolConfig


class TestAdapterFactory:
    """Test adapter factory functions."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="test", api_key_env="TEST_KEY", timeout=30, default_top_k=5
        )

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_create_vectara_adapter(self, tool_config):
        """Test creating Vectara adapter (with mawsuah corpus)."""
        tool_config.name = "mawsuah"
        tool_config.adapter = "vectara"  # Specify which adapter to use
        tool_config.api_key_env = "VECTARA_API_KEY"
        tool_config.corpus_id = "test_corpus"

        adapter = create_adapter("mawsuah", tool_config)
        assert adapter.name == "mawsuah"
        assert adapter.__class__.__name__ == "VectaraAdapter"

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    @patch("ragdiff.adapters.goodmem.GOODMEM_AVAILABLE", False)
    def test_create_goodmem_adapter(self, tool_config):
        """Test creating Goodmem adapter."""
        tool_config.name = "goodmem"
        tool_config.api_key_env = "GOODMEM_API_KEY"

        adapter = create_adapter("goodmem", tool_config)
        assert adapter.name == "goodmem"
        assert adapter.__class__.__name__ == "GoodmemAdapter"

    def test_create_unknown_adapter(self, tool_config):
        """Test error when creating unknown adapter."""
        with pytest.raises(AdapterRegistryError, match="Unknown adapter: nonexistent"):
            create_adapter("nonexistent", tool_config)

    def test_get_available_adapters(self):
        """Test getting list of available adapters."""
        adapters = get_available_adapters()
        assert "vectara" in adapters
        assert "goodmem" in adapters
        assert "agentset" in adapters
        assert isinstance(adapters, list)


class TestAdapterVariants:
    """Test adapter variants feature."""

    @pytest.fixture
    def base_config(self):
        """Create base test configuration."""
        return ToolConfig(
            name="test-variant",
            api_key_env="VECTARA_API_KEY",
            corpus_id="test_corpus",
            timeout=30,
            default_top_k=5,
        )

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_backward_compatibility_no_adapter_field(self, base_config):
        """Test that configs without adapter field work (backward compatibility)."""
        # When adapter field is not set, it should default to tool name
        base_config.name = "vectara"
        base_config.adapter = None  # Explicitly None

        adapter = create_adapter("vectara", base_config)
        assert adapter.name == "vectara"
        assert adapter.__class__.__name__ == "VectaraAdapter"

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_variant_with_explicit_adapter(self, base_config):
        """Test variant using explicit adapter field."""
        # Display name is "tafsir-corpus" but uses vectara adapter
        base_config.name = "tafsir-corpus"
        base_config.adapter = "vectara"

        adapter = create_adapter("tafsir-corpus", base_config)
        assert adapter.name == "tafsir-corpus"
        assert adapter.__class__.__name__ == "VectaraAdapter"

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_multiple_variants_same_adapter(self, base_config):
        """Test multiple variants using the same adapter."""
        # Create two variants of vectara with different display names
        variant1_config = ToolConfig(
            name="tafsir-corpus",
            adapter="vectara",
            api_key_env="VECTARA_API_KEY",
            corpus_id="tafsir_v1",
            timeout=30,
            default_top_k=5,
        )

        variant2_config = ToolConfig(
            name="mawsuah-corpus",
            adapter="vectara",
            api_key_env="VECTARA_API_KEY",
            corpus_id="mawsuah_v1",
            timeout=30,
            default_top_k=5,
        )

        adapter1 = create_adapter("tafsir-corpus", variant1_config)
        adapter2 = create_adapter("mawsuah-corpus", variant2_config)

        # Both should be VectaraAdapter but with different display names
        assert adapter1.__class__.__name__ == "VectaraAdapter"
        assert adapter2.__class__.__name__ == "VectaraAdapter"
        assert adapter1.name == "tafsir-corpus"
        assert adapter2.name == "mawsuah-corpus"
        assert adapter1.corpus_id == "tafsir_v1"
        assert adapter2.corpus_id == "mawsuah_v1"

    @patch.dict(
        os.environ,
        {"AGENTSET_API_TOKEN": "test_token", "AGENTSET_NAMESPACE_ID": "test_ns"},
    )
    @patch("ragdiff.adapters.agentset.Agentset")
    def test_variant_with_options(self, mock_agentset_class, base_config):
        """Test that adapter options are passed correctly."""
        # Create agentset variant with custom options
        config_with_options = ToolConfig(
            name="agentset-rerank",
            adapter="agentset",
            api_key_env="AGENTSET_API_TOKEN",
            namespace_id_env="AGENTSET_NAMESPACE_ID",
            options={"rerank": False},
            timeout=30,
            default_top_k=5,
        )

        adapter = create_adapter("agentset-rerank", config_with_options)

        # Verify adapter was created with correct name
        assert adapter.name == "agentset-rerank"
        assert adapter.__class__.__name__ == "AgentsetAdapter"

        # Verify options were parsed (AgentsetAdapter should have rerank=False)
        assert hasattr(adapter, "rerank")
        assert adapter.rerank is False

    @patch.dict(
        os.environ,
        {"AGENTSET_API_TOKEN": "test_token", "AGENTSET_NAMESPACE_ID": "test_ns"},
    )
    @patch("ragdiff.adapters.agentset.Agentset")
    def test_variant_without_options_uses_defaults(
        self, mock_agentset_class, base_config
    ):
        """Test that adapters use defaults when no options provided."""
        config_no_options = ToolConfig(
            name="agentset-default",
            adapter="agentset",
            api_key_env="AGENTSET_API_TOKEN",
            namespace_id_env="AGENTSET_NAMESPACE_ID",
            options=None,  # No options
            timeout=30,
            default_top_k=5,
        )

        adapter = create_adapter("agentset-default", config_no_options)

        # Verify default rerank value is True
        assert hasattr(adapter, "rerank")
        assert adapter.rerank is True

    def test_unknown_adapter_in_variant(self, base_config):
        """Test error when variant specifies unknown adapter."""
        base_config.name = "my-variant"
        base_config.adapter = "nonexistent"

        with pytest.raises(AdapterRegistryError, match="Unknown adapter: nonexistent"):
            create_adapter("my-variant", base_config)
