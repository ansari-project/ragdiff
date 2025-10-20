"""Mock SearchVectara base class for testing without Ansari dependencies.

This mimics the interface from Ansari Backend.
In production, this would be imported from ansari.tools.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class SearchVectara(ABC):
    """Base class for Vectara-based search tools.

    This is a mock of the actual SearchVectara from Ansari Backend.
    Replace with actual import when integrating: from ansari.tools import SearchVectara
    """

    def __init__(
        self,
        api_key: str,
        corpus_id: str,
        customer_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize Vectara search tool.

        Args:
            api_key: Vectara API key
            corpus_id: Vectara corpus ID
            customer_id: Optional Vectara customer ID (not required in v2 API)
            base_url: Optional custom base URL
        """
        self.api_key = api_key
        self.corpus_id = corpus_id
        self.customer_id = customer_id  # Optional in v2 API
        self.base_url = base_url or "https://api.vectara.io"

    @abstractmethod
    def run(self, query: str, **kwargs) -> dict[str, Any]:
        """Execute search query.

        Args:
            query: Search query string
            **kwargs: Additional parameters

        Returns:
            Raw response from Vectara API
        """
        pass

    @abstractmethod
    def format_as_tool_result(self, results: dict[str, Any]) -> str:
        """Format results for tool usage.

        Args:
            results: Raw API response

        Returns:
            Formatted string for display
        """
        pass

    def format_as_ref_list(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Format results as reference list.

        Args:
            results: Raw API response

        Returns:
            List of reference documents
        """
        # Default implementation
        documents = results.get("documents", [])
        return documents if isinstance(documents, list) else []
