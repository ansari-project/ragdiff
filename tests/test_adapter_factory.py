"""Tests for adapter factory."""

import pytest
import os
from unittest.mock import patch, Mock

from src.adapters.factory import (
    create_adapter,
    register_adapter,
    get_available_adapters,
    ADAPTER_REGISTRY
)
from src.adapters.base import BaseRagTool
from src.core.models import ToolConfig


class TestAdapterFactory:
    """Test adapter factory functions."""

    @pytest.fixture
    def tool_config(self):
        """Create test configuration."""
        return ToolConfig(
            name="test",
            api_key_env="TEST_KEY",
            timeout=30,
            default_top_k=5
        )

    @patch.dict(os.environ, {"VECTARA_API_KEY": "test_key"})
    def test_create_mawsuah_adapter(self, tool_config):
        """Test creating Mawsuah adapter."""
        tool_config.name = "mawsuah"
        tool_config.api_key_env = "VECTARA_API_KEY"
        tool_config.customer_id = "test_customer"
        tool_config.corpus_id = "test_corpus"

        adapter = create_adapter("mawsuah", tool_config)
        assert adapter.name == "mawsuah"
        assert adapter.__class__.__name__ == "MawsuahAdapter"

    @patch.dict(os.environ, {"GOODMEM_API_KEY": "test_key"})
    @patch('src.adapters.goodmem.GOODMEM_AVAILABLE', False)
    def test_create_goodmem_adapter(self, tool_config):
        """Test creating Goodmem adapter."""
        tool_config.name = "goodmem"
        tool_config.api_key_env = "GOODMEM_API_KEY"

        adapter = create_adapter("goodmem", tool_config)
        assert adapter.name == "goodmem"
        assert adapter.__class__.__name__ == "GoodmemAdapter"

    def test_create_unknown_adapter(self, tool_config):
        """Test error when creating unknown adapter."""
        with pytest.raises(ValueError, match="Unknown tool: nonexistent"):
            create_adapter("nonexistent", tool_config)

    @patch.dict(os.environ, {"TEST_KEY": "test"})
    def test_create_adapter_initialization_error(self, tool_config):
        """Test error handling during adapter initialization."""
        # Mock an adapter that fails during init
        class FailingAdapter(BaseRagTool):
            def __init__(self, config):
                raise RuntimeError("Init failed")

            def search(self, query, top_k=5):
                pass

        # Temporarily register the failing adapter
        original = ADAPTER_REGISTRY.get("failing")
        ADAPTER_REGISTRY["failing"] = FailingAdapter

        try:
            with pytest.raises(RuntimeError, match="Init failed"):
                create_adapter("failing", tool_config)
        finally:
            # Restore registry
            if original:
                ADAPTER_REGISTRY["failing"] = original
            else:
                ADAPTER_REGISTRY.pop("failing", None)

    def test_register_adapter(self):
        """Test registering new adapter."""
        class CustomAdapter(BaseRagTool):
            def search(self, query, top_k=5):
                return []

        # Register new adapter
        original = ADAPTER_REGISTRY.get("custom")
        try:
            register_adapter("custom", CustomAdapter)
            assert "custom" in ADAPTER_REGISTRY
            assert ADAPTER_REGISTRY["custom"] == CustomAdapter
        finally:
            # Cleanup
            if original:
                ADAPTER_REGISTRY["custom"] = original
            else:
                ADAPTER_REGISTRY.pop("custom", None)

    def test_register_duplicate_adapter(self):
        """Test error when registering duplicate adapter."""
        with pytest.raises(ValueError, match="already registered"):
            register_adapter("mawsuah", Mock)

    def test_register_invalid_adapter(self):
        """Test error when registering non-BaseRagTool class."""
        class NotAnAdapter:
            pass

        with pytest.raises(TypeError, match="must be a subclass of BaseRagTool"):
            register_adapter("invalid", NotAnAdapter)

    def test_get_available_adapters(self):
        """Test getting list of available adapters."""
        adapters = get_available_adapters()
        assert "mawsuah" in adapters
        assert "goodmem" in adapters
        assert isinstance(adapters, list)