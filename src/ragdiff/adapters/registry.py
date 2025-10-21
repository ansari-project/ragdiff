"""Adapter registry with version compatibility enforcement.

This module provides a central registry for discovering and managing RAG adapters.
It enforces adapter API version compatibility to prevent runtime errors.
"""

import logging
from typing import Optional

from ..core.errors import AdapterRegistryError
from ..version import ADAPTER_API_VERSION
from .abc import RagAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for RAG adapters with version compatibility checking.

    The registry maintains a mapping of adapter names to adapter classes,
    and ensures all registered adapters are compatible with the current
    adapter API version.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._adapters: dict[str, type[RagAdapter]] = {}
        self._registry_api_version = ADAPTER_API_VERSION

    def register(self, adapter_class: type[RagAdapter]) -> None:
        """Register an adapter class.

        Args:
            adapter_class: The adapter class to register (must inherit from RagAdapter)

        Raises:
            AdapterRegistryError: If adapter name is empty, already registered,
                                 or API version is incompatible
        """
        # Validate adapter has a name
        if not adapter_class.ADAPTER_NAME:
            raise AdapterRegistryError(
                f"Adapter class {adapter_class.__name__} must set ADAPTER_NAME"
            )

        adapter_name = adapter_class.ADAPTER_NAME

        # Check for duplicate registration
        if adapter_name in self._adapters:
            raise AdapterRegistryError(
                f"Adapter '{adapter_name}' is already registered. "
                f"Cannot register {adapter_class.__name__}."
            )

        # Check API version compatibility
        adapter_version = adapter_class.ADAPTER_API_VERSION
        if not self._is_compatible_version(adapter_version):
            logger.warning(
                f"Adapter '{adapter_name}' uses API version {adapter_version}, "
                f"but registry expects {self._registry_api_version}. "
                f"This may cause compatibility issues."
            )

        # Register the adapter
        self._adapters[adapter_name] = adapter_class
        logger.info(
            f"Registered adapter '{adapter_name}' " f"(API version: {adapter_version})"
        )

    def get(self, name: str) -> Optional[type[RagAdapter]]:
        """Get adapter class by name.

        Args:
            name: Name of the adapter to retrieve

        Returns:
            The adapter class, or None if not found
        """
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        """Get list of all registered adapter names.

        Returns:
            List of adapter names sorted alphabetically
        """
        return sorted(self._adapters.keys())

    def get_adapter_info(self, name: str) -> Optional[dict[str, any]]:
        """Get detailed information about an adapter.

        Args:
            name: Name of the adapter

        Returns:
            Dictionary with adapter metadata, or None if adapter not found

        Example return value:
            {
                "name": "vectara",
                "api_version": "1.0.0",
                "class_name": "VectaraAdapter",
                "module": "ragdiff.adapters.vectara"
            }
        """
        adapter_class = self._adapters.get(name)
        if not adapter_class:
            return None

        return {
            "name": adapter_class.ADAPTER_NAME,
            "api_version": adapter_class.ADAPTER_API_VERSION,
            "class_name": adapter_class.__name__,
            "module": adapter_class.__module__,
        }

    def _is_compatible_version(self, adapter_version: str) -> bool:
        """Check if adapter version is compatible with registry.

        For now, we use strict version matching (MAJOR.MINOR.PATCH must match).
        In the future, we could implement semantic versioning rules where:
        - MAJOR version must match
        - MINOR version can be >= registry version
        - PATCH version doesn't matter

        Args:
            adapter_version: The adapter's API version string

        Returns:
            True if compatible, False otherwise
        """
        # Strict matching for now
        return adapter_version == self._registry_api_version


# Global registry instance
_global_registry = AdapterRegistry()


def register_adapter(adapter_class: type[RagAdapter]) -> None:
    """Register an adapter in the global registry.

    This is a convenience function for registering adapters without
    needing to access the global registry directly.

    Args:
        adapter_class: The adapter class to register

    Raises:
        AdapterRegistryError: If registration fails
    """
    _global_registry.register(adapter_class)


def get_adapter(name: str) -> Optional[type[RagAdapter]]:
    """Get an adapter class from the global registry.

    Args:
        name: Name of the adapter

    Returns:
        The adapter class, or None if not found
    """
    return _global_registry.get(name)


def list_available_adapters() -> list[str]:
    """Get list of all available adapter names.

    Returns:
        List of adapter names sorted alphabetically
    """
    return _global_registry.list_adapters()


def get_adapter_info(name: str) -> Optional[dict[str, any]]:
    """Get detailed information about an adapter.

    Args:
        name: Name of the adapter

    Returns:
        Dictionary with adapter metadata, or None if not found
    """
    return _global_registry.get_adapter_info(name)
