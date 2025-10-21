"""Tests for Phase 1: Foundation

Tests cover:
- Version module
- Error hierarchy
- Adapter ABC
- Adapter registry with version enforcement
"""

import pytest

from ragdiff.adapters.abc import RagAdapter
from ragdiff.adapters.registry import (
    AdapterRegistry,
    get_adapter,
    get_adapter_info,
    list_available_adapters,
    register_adapter,
)
from ragdiff.core.errors import (
    AdapterError,
    AdapterRegistryError,
    ConfigurationError,
    EvaluationError,
    RagDiffError,
    ValidationError,
)
from ragdiff.version import ADAPTER_API_VERSION, __version__


class TestVersionModule:
    """Test version module."""

    def test_package_version_exists(self):
        """Package version should be defined."""
        assert __version__
        assert isinstance(__version__, str)

    def test_package_version_format(self):
        """Package version should follow semver format."""
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    def test_adapter_api_version_exists(self):
        """Adapter API version should be defined."""
        assert ADAPTER_API_VERSION
        assert isinstance(ADAPTER_API_VERSION, str)

    def test_adapter_api_version_format(self):
        """Adapter API version should follow semver format."""
        parts = ADAPTER_API_VERSION.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestErrorHierarchy:
    """Test error class hierarchy."""

    def test_ragdiff_error_is_exception(self):
        """RagDiffError should inherit from Exception."""
        assert issubclass(RagDiffError, Exception)

    def test_configuration_error_inheritance(self):
        """ConfigurationError should inherit from RagDiffError."""
        assert issubclass(ConfigurationError, RagDiffError)

    def test_adapter_error_inheritance(self):
        """AdapterError should inherit from RagDiffError."""
        assert issubclass(AdapterError, RagDiffError)

    def test_adapter_registry_error_inheritance(self):
        """AdapterRegistryError should inherit from RagDiffError."""
        assert issubclass(AdapterRegistryError, RagDiffError)

    def test_validation_error_inheritance(self):
        """ValidationError should inherit from RagDiffError."""
        assert issubclass(ValidationError, RagDiffError)

    def test_evaluation_error_inheritance(self):
        """EvaluationError should inherit from RagDiffError."""
        assert issubclass(EvaluationError, RagDiffError)

    def test_can_catch_all_with_ragdiff_error(self):
        """All custom errors should be catchable with RagDiffError."""
        errors = [
            ConfigurationError("test"),
            AdapterError("test"),
            AdapterRegistryError("test"),
            ValidationError("test"),
            EvaluationError("test"),
        ]

        for error in errors:
            try:
                raise error
            except RagDiffError:
                pass  # Successfully caught
            else:
                pytest.fail(f"{type(error).__name__} was not caught by RagDiffError")


class TestAdapterABC:
    """Test RagAdapter abstract base class."""

    def test_cannot_instantiate_abc(self):
        """Cannot instantiate abstract RagAdapter directly."""
        with pytest.raises(TypeError):
            RagAdapter()

    def test_adapter_api_version_attribute(self):
        """RagAdapter should have ADAPTER_API_VERSION attribute."""
        assert hasattr(RagAdapter, "ADAPTER_API_VERSION")
        assert RagAdapter.ADAPTER_API_VERSION == "1.0.0"

    def test_adapter_name_attribute(self):
        """RagAdapter should have ADAPTER_NAME attribute."""
        assert hasattr(RagAdapter, "ADAPTER_NAME")

    def test_must_implement_search(self):
        """Subclass must implement search method."""

        class IncompleteAdapter(RagAdapter):
            ADAPTER_NAME = "incomplete"

            def validate_config(self, config):
                pass

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_must_implement_validate_config(self):
        """Subclass must implement validate_config method."""

        class IncompleteAdapter(RagAdapter):
            ADAPTER_NAME = "incomplete"

            def search(self, query, top_k=5):
                return []

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_complete_adapter_can_be_instantiated(self):
        """Complete adapter implementation can be instantiated."""

        class CompleteAdapter(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "complete"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        adapter = CompleteAdapter()
        assert adapter.ADAPTER_NAME == "complete"
        assert adapter.ADAPTER_API_VERSION == "1.0.0"


class TestAdapterRegistry:
    """Test adapter registry with version enforcement."""

    def test_registry_initialization(self):
        """Registry should initialize empty."""
        registry = AdapterRegistry()
        assert registry.list_adapters() == []

    def test_register_valid_adapter(self):
        """Should successfully register a valid adapter."""

        class TestAdapter(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "test"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        registry.register(TestAdapter)

        assert "test" in registry.list_adapters()
        assert registry.get("test") == TestAdapter

    def test_register_adapter_without_name(self):
        """Should raise error if adapter has no name."""

        class NoNameAdapter(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = ""  # Empty name

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        with pytest.raises(AdapterRegistryError, match="must set ADAPTER_NAME"):
            registry.register(NoNameAdapter)

    def test_register_duplicate_name(self):
        """Should raise error on duplicate adapter name."""

        class Adapter1(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "duplicate"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        class Adapter2(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "duplicate"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        registry.register(Adapter1)

        with pytest.raises(AdapterRegistryError, match="already registered"):
            registry.register(Adapter2)

    def test_version_compatibility_check(self, caplog):
        """Should warn when adapter version mismatches."""

        class OldVersionAdapter(RagAdapter):
            ADAPTER_API_VERSION = "0.9.0"  # Old version
            ADAPTER_NAME = "oldversion"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        registry.register(OldVersionAdapter)

        # Should still register but log warning
        assert "oldversion" in registry.list_adapters()
        assert "compatibility issues" in caplog.text.lower()

    def test_get_nonexistent_adapter(self):
        """Should return None for nonexistent adapter."""
        registry = AdapterRegistry()
        assert registry.get("nonexistent") is None

    def test_list_adapters_sorted(self):
        """Should return sorted list of adapter names."""

        class AdapterZ(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "zebra"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        class AdapterA(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "apple"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        registry.register(AdapterZ)
        registry.register(AdapterA)

        assert registry.list_adapters() == ["apple", "zebra"]

    def test_get_adapter_info(self):
        """Should return detailed adapter information."""

        class InfoTestAdapter(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "infotest"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        registry = AdapterRegistry()
        registry.register(InfoTestAdapter)

        info = registry.get_adapter_info("infotest")
        assert info is not None
        assert info["name"] == "infotest"
        assert info["api_version"] == "1.0.0"
        assert info["class_name"] == "InfoTestAdapter"
        assert "module" in info

    def test_get_adapter_info_nonexistent(self):
        """Should return None for nonexistent adapter info."""
        registry = AdapterRegistry()
        assert registry.get_adapter_info("nonexistent") is None


class TestGlobalRegistryFunctions:
    """Test global registry convenience functions."""

    def test_global_functions_use_same_registry(self):
        """Global functions should share the same registry instance."""

        class GlobalTestAdapter(RagAdapter):
            ADAPTER_API_VERSION = "1.0.0"
            ADAPTER_NAME = "globaltest"

            def search(self, query, top_k=5):
                return []

            def validate_config(self, config):
                pass

        # Register using global function
        register_adapter(GlobalTestAdapter)

        # Retrieve using global function
        adapter_class = get_adapter("globaltest")
        assert adapter_class == GlobalTestAdapter

        # Should appear in list
        assert "globaltest" in list_available_adapters()

        # Should have info
        info = get_adapter_info("globaltest")
        assert info is not None
        assert info["name"] == "globaltest"
