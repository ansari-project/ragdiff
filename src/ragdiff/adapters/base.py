"""Base adapter for RAG tools."""

import logging
import os
import time
from abc import abstractmethod
from typing import Any

from ..core.models import RagResult, ToolConfig

# Use mock for now, replace with actual import in production:
# from ansari.tools import SearchVectara
from .search_vectara_mock import SearchVectara

logger = logging.getLogger(__name__)


class BaseRagTool(SearchVectara):
    """Base adapter that conforms to SearchVectara interface.

    This ensures compatibility with Ansari Backend while providing
    normalized interfaces for comparison.
    """

    def __init__(self, config: ToolConfig):
        """Initialize with tool configuration.

        Args:
            config: Tool configuration object
        """
        self.config = config
        self._validate_credentials()

        # Get credentials from environment
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ValueError(
                f"Missing API key environment variable: {config.api_key_env}"
            )

        # Initialize parent with Vectara-compatible parameters
        # Note: customer_id is no longer required in Vectara v2 API
        super().__init__(
            api_key=api_key,
            corpus_id=config.corpus_id or "",
            customer_id=config.customer_id,  # Optional in v2 API
            base_url=config.base_url,
        )

        self.name = config.name
        self.timeout = config.timeout
        self.max_retries = config.max_retries
        self.default_top_k = config.default_top_k

    def _validate_credentials(self) -> None:
        """Validate required credentials are available."""
        if not os.getenv(self.config.api_key_env):
            raise ValueError(
                f"Missing required environment variable: {self.config.api_key_env}\n"
                f"Please set it with your {self.config.name} API key."
            )

    def run(self, query: str, **kwargs) -> dict[str, Any]:
        """Execute search matching SearchVectara interface.

        Args:
            query: Search query
            **kwargs: Additional parameters like top_k

        Returns:
            Raw API response
        """
        top_k = kwargs.get("top_k", self.default_top_k)

        # Measure latency
        start_time = time.time()

        try:
            # Call the search implementation
            results = self.search(query, top_k=top_k)

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Convert to expected format
            return {
                "results": results,
                "latency_ms": latency_ms,
                "query": query,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Search failed for {self.name}: {str(e)}")
            latency_ms = (time.time() - start_time) * 1000

            return {
                "results": [],
                "latency_ms": latency_ms,
                "query": query,
                "success": False,
                "error": str(e),
            }

    def format_as_tool_result(self, results: dict[str, Any]) -> str:
        """Format results for tool display.

        Args:
            results: Raw API response

        Returns:
            Formatted string
        """
        if not results.get("success", False):
            return f"Error: {results.get('error', 'Unknown error')}"

        result_list = results.get("results", [])
        if not result_list:
            return "No results found."

        formatted = []
        for i, result in enumerate(result_list[:5], 1):
            if isinstance(result, RagResult):
                formatted.append(f"{i}. [{result.score:.2f}] {result.text[:200]}...")
            else:
                # Handle dict format
                formatted.append(f"{i}. {str(result)[:200]}...")

        return "\n".join(formatted)

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search implementation to be overridden by subclasses.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of normalized RagResult objects
        """
        pass

    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1 range.

        Args:
            score: Raw score

        Returns:
            Normalized score
        """
        if 0 <= score <= 1:
            return score
        elif score > 100:
            return min(score / 1000, 1.0)  # Assume out of 1000
        elif score > 1:
            return min(score / 100, 1.0)  # Assume percentage
        else:
            return max(0, score)  # Clamp negative
