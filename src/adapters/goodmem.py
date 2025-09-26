"""Goodmem adapter for RAG search."""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
import logging

from .base import BaseRagTool
from ..core.models import RagResult, ToolConfig

logger = logging.getLogger(__name__)

# Import will be conditional based on availability
try:
    from goodmem import Client as GoodmemClient
    GOODMEM_AVAILABLE = True
except ImportError:
    GOODMEM_AVAILABLE = False
    logger.warning("goodmem-client not installed. Using mock implementation.")


class GoodmemAdapter(BaseRagTool):
    """Adapter for Goodmem search tool."""

    def __init__(self, config: ToolConfig):
        """Initialize Goodmem adapter.

        Args:
            config: Tool configuration
        """
        super().__init__(config)
        self.description = "Next-generation RAG system using Goodmem"

        # Initialize Goodmem client if available
        if GOODMEM_AVAILABLE:
            self.client = GoodmemClient(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Running in mock mode - install goodmem-client for real functionality")

    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        """Search Goodmem for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        if not GOODMEM_AVAILABLE or not self.client:
            # Mock implementation for testing
            return self._mock_search(query, top_k)

        try:
            # Handle potential async client
            if asyncio.iscoroutinefunction(self.client.search):
                # Run async search in sync context
                results = asyncio.run(self._async_search(query, top_k))
            else:
                # Synchronous search
                results = self._sync_search(query, top_k)

            return results

        except Exception as e:
            logger.error(f"Goodmem search failed: {str(e)}")
            raise

    async def _async_search(self, query: str, top_k: int) -> List[RagResult]:
        """Handle async Goodmem search.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of normalized results
        """
        response = await self.client.search(
            query=query,
            limit=top_k
        )
        return self._parse_goodmem_response(response)

    def _sync_search(self, query: str, top_k: int) -> List[RagResult]:
        """Handle synchronous Goodmem search.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of normalized results
        """
        response = self.client.search(
            query=query,
            limit=top_k
        )
        return self._parse_goodmem_response(response)

    def _parse_goodmem_response(self, response: Any) -> List[RagResult]:
        """Parse Goodmem API response into normalized results.

        Args:
            response: Raw API response from Goodmem

        Returns:
            List of normalized RagResult objects
        """
        results = []

        # Handle different possible response formats
        # This is a best guess - actual format will depend on goodmem-client
        if hasattr(response, 'results'):
            items = response.results
        elif isinstance(response, dict):
            items = response.get('results', response.get('documents', []))
        elif isinstance(response, list):
            items = response
        else:
            logger.warning(f"Unknown Goodmem response format: {type(response)}")
            return results

        for idx, item in enumerate(items):
            try:
                # Extract fields based on possible formats
                if hasattr(item, '__dict__'):
                    # Object with attributes
                    text = getattr(item, 'text', getattr(item, 'content', str(item)))
                    score = getattr(item, 'score', getattr(item, 'relevance', 0.5))
                    doc_id = getattr(item, 'id', f"goodmem_{idx}")
                    source = getattr(item, 'source', getattr(item, 'url', 'Goodmem'))
                    metadata = getattr(item, 'metadata', {})
                elif isinstance(item, dict):
                    # Dictionary format
                    text = item.get('text', item.get('content', str(item)))
                    score = item.get('score', item.get('relevance', 0.5))
                    doc_id = item.get('id', f"goodmem_{idx}")
                    source = item.get('source', item.get('url', 'Goodmem'))
                    metadata = item.get('metadata', {})
                else:
                    # Unknown format - try to convert to string
                    text = str(item)
                    score = 0.5
                    doc_id = f"goodmem_{idx}"
                    source = "Goodmem"
                    metadata = {}

                result = RagResult(
                    id=str(doc_id),
                    text=text,
                    score=self._normalize_score(score),
                    source=source,
                    metadata=metadata
                )
                results.append(result)

            except Exception as e:
                logger.warning(f"Failed to parse Goodmem result item: {e}")
                continue

        return results

    def _mock_search(self, query: str, top_k: int) -> List[RagResult]:
        """Mock search for testing without Goodmem client.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Mock results for testing
        """
        mock_results = []
        for i in range(min(top_k, 3)):
            mock_results.append(
                RagResult(
                    id=f"goodmem_mock_{i}",
                    text=f"Mock Goodmem result {i+1} for query: {query}. "
                         f"This is a placeholder result for testing purposes. "
                         f"Install goodmem-client to get real results.",
                    score=0.9 - (i * 0.15),
                    source=f"Goodmem Mock Source {i+1}",
                    metadata={
                        "mock": True,
                        "index": i,
                        "query": query
                    }
                )
            )
        return mock_results