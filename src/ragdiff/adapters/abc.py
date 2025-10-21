"""Abstract base class for RAG adapters.

This module defines the stable adapter interface that all RAG system adapters
must implement. The interface is versioned to support backwards compatibility.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..core.models import RagResult


class RagAdapter(ABC):
    """Abstract base class for all RAG system adapters.

    All adapters must implement this interface to ensure compatibility
    with the RAGDiff framework.

    Attributes:
        ADAPTER_API_VERSION: Version of the adapter API this adapter implements.
                            Must match the registry's supported version.
        ADAPTER_NAME: Unique name for this adapter (e.g., "vectara", "goodmem").
    """

    # Class attributes that must be set by subclasses
    ADAPTER_API_VERSION: str = "1.0.0"
    ADAPTER_NAME: str = ""  # Must be overridden by subclass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Execute a search query and return normalized results.

        Args:
            query: The search query string
            top_k: Maximum number of results to return

        Returns:
            List of RagResult objects, sorted by relevance score (descending)

        Raises:
            AdapterError: If the search fails due to network, auth, or API issues
            ValidationError: If the query or top_k parameters are invalid
        """
        pass

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate adapter configuration.

        This method should check that all required configuration fields are
        present and valid. It should raise ConfigurationError with a clear
        message if anything is wrong.

        Args:
            config: Configuration dictionary for this adapter

        Raises:
            ConfigurationError: If configuration is invalid or incomplete

        Returns:
            None (raises exception on validation failure)
        """
        pass

    def get_required_env_vars(self) -> list[str]:
        """Get list of required environment variable names.

        Returns:
            List of environment variable names required by this adapter
            (e.g., ["VECTARA_API_KEY", "VECTARA_CORPUS_ID"])
        """
        return []

    def get_options_schema(self) -> dict[str, Any]:
        """Get JSON schema for adapter-specific configuration options.

        Returns:
            JSON schema dictionary describing valid configuration options.
            Empty dict if no options beyond the standard ones.

        Example:
            {
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Vectara corpus ID"},
                    "timeout": {"type": "integer", "minimum": 1, "default": 60}
                },
                "required": ["corpus_id"]
            }
        """
        return {}
