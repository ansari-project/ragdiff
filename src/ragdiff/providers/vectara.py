"""Vectara provider for RAGDiff v2.0.

Vectara is a RAG platform that provides semantic search over document corpora.
This provider connects to Vectara's v2 API.

Configuration:
    api_key: Vectara API key (string, required)
    corpus_id: Corpus identifier (string, required)
    base_url: API base URL (string, optional, default: "https://api.vectara.io")
    timeout: Request timeout in seconds (int, optional, default: 60)

Example:
    >>> provider = VectaraProvider(config={
    ...     "api_key": "vsk_...",
    ...     "corpus_id": "my-corpus",
    ...     "timeout": 30
    ... })
    >>> chunks = provider.search("What is Islamic law?", top_k=5)
"""

from typing import Any, Optional

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import RetrievedChunk
from .abc import Provider

logger = get_logger(__name__)


class VectaraProvider(Provider):
    """Vectara RAG provider implementation.

    Uses Vectara's v2 API for semantic search over document corpora.
    Supports custom corpus configuration for different knowledge domains.
    """

    def __init__(self, config: dict):
        """Initialize Vectara provider.

        Args:
            config: Configuration dictionary with:
                - api_key (str, required): Vectara API key
                - corpus_id (str, required): Corpus identifier
                - base_url (str, optional): API base URL
                - timeout (int, optional): Request timeout in seconds

        Raises:
            ConfigError: If required config missing or invalid
        """
        super().__init__(config)

        # Validate required fields
        if "api_key" not in config:
            raise ConfigError("Vectara config missing required field: api_key")
        if "corpus_id" not in config:
            raise ConfigError("Vectara config missing required field: corpus_id")

        # Store configuration
        self.api_key = config["api_key"]
        self.corpus_id = config["corpus_id"]
        self.base_url = config.get("base_url", "https://api.vectara.io")
        self.timeout = config.get("timeout", 60)

        # Lazy load requests
        self.requests: Optional[Any] = None

        logger.debug(f"Initialized VectaraProvider with corpus_id={self.corpus_id}")

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search Vectara corpus for relevant documents.

        Args:
            query: Search query text
            top_k: Maximum number of results to return

        Returns:
            List of RetrievedChunk objects with content, score, and metadata

        Raises:
            RunError: If API request fails
        """
        # Lazy load requests on first use
        if self.requests is None:
            try:
                import requests

                self.requests = requests
            except ImportError as e:
                raise RunError(
                    f"requests library is required for Vectara provider. "
                    f"Install with: pip install requests. Error: {e}"
                ) from e

        try:
            # Prepare Vectara v2 API request
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": self.api_key,
            }

            request_body = {
                "query": query,
                "search": {"corpora": [{"corpus_key": self.corpus_id}], "limit": top_k},
            }

            logger.debug(f"Vectara API request: query='{query[:50]}...', top_k={top_k}")

            # Make API request
            response = self.requests.post(
                f"{self.base_url}/v2/query",
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()

            # Parse response into RetrievedChunk objects
            chunks = []
            for doc in data.get("search_results", [])[:top_k]:
                # Extract text and score
                text = doc.get("text", "")
                score = doc.get("score", 0.0)

                # Combine part and document metadata
                metadata = {}
                if doc.get("part_metadata"):
                    metadata.update(doc["part_metadata"])
                if doc.get("document_metadata"):
                    metadata.update(doc["document_metadata"])

                # Add document ID to metadata
                if doc.get("document_id"):
                    metadata["document_id"] = doc["document_id"]

                # Create chunk
                chunk = RetrievedChunk(content=text, score=score, metadata=metadata)
                chunks.append(chunk)

            logger.info(
                f"Vectara returned {len(chunks)} chunks for query: '{query[:50]}...'"
            )
            return chunks

        except self.requests.exceptions.Timeout as e:
            logger.error(f"Vectara API timeout: {e}")
            raise RunError(f"Vectara API timeout after {self.timeout}s: {e}") from e

        except self.requests.exceptions.HTTPError as e:
            logger.error(f"Vectara API HTTP error: {e}")
            if e.response.status_code == 401:
                raise RunError(
                    "Vectara authentication failed. Check your API key."
                ) from e
            elif e.response.status_code == 404:
                raise RunError(f"Vectara corpus not found: {self.corpus_id}") from e
            else:
                raise RunError(
                    f"Vectara API error ({e.response.status_code}): {e}"
                ) from e

        except self.requests.exceptions.RequestException as e:
            logger.error(f"Vectara API request failed: {e}")
            raise RunError(f"Vectara API request failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in Vectara search: {e}")
            raise RunError(f"Unexpected error in Vectara search: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"VectaraProvider(corpus_id='{self.corpus_id}')"


# Register the tool
from .registry import register_tool

register_tool("vectara", VectaraProvider)
