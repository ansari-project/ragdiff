"""Provider abstract base class for RAGDiff v2.0.

A Provider is a RAG service/platform (like Vectara, MongoDB, Agentset) configured
with specific settings. Providers implement a simple interface: search(query, top_k).

Example:
    >>> provider = VectaraProvider(config={
    ...     "api_key": "...",
    ...     "corpus_id": 123,
    ... })
    >>> chunks = provider.search("What is Islamic law?", top_k=5)
    >>> for chunk in chunks:
    ...     print(f"Score: {chunk.score}, Content: {chunk.content[:100]}")
"""

from abc import ABC, abstractmethod
from typing import Union

from ..core.models import RetrievedChunk, SearchResult


class Provider(ABC):
    """Abstract base class for all RAG providers.

    A Provider wraps a RAG service/platform (Vectara, MongoDB, Agentset, etc.) with
    specific configuration. All providers must implement the search() method.

    Providers are instantiated from ProviderConfig objects and registered in the
    TOOL_REGISTRY for discovery.

    Thread Safety:
        Providers must be thread-safe for parallel query execution. If your
        underlying client is not thread-safe, use locks or create per-query
        clients.

    Attributes:
        config: Dictionary of provider-specific configuration (API keys, endpoints, etc.)

    Example:
        class MyProvider(Provider):
            def __init__(self, config: dict):
                self.config = config
                self.client = MyClient(api_key=config["api_key"])

            def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
                results = self.client.search(query, limit=top_k)
                return [
                    RetrievedChunk(
                        content=r.text,
                        score=r.score,
                        metadata={"doc_id": r.doc_id}
                    )
                    for r in results
                ]
    """

    def __init__(self, config: dict):
        """Initialize the provider with configuration.

        Args:
            config: Provider-specific configuration dictionary (API keys, endpoints, etc.)

        Raises:
            ConfigError: If required configuration is missing or invalid
        """
        self.config = config

    @abstractmethod
    def search(
        self, query: str, top_k: int = 5
    ) -> Union[list[RetrievedChunk], SearchResult]:
        """Execute search and return ranked chunks with metadata.

        Args:
            query: The search query text
            top_k: Maximum number of results to return (default: 5)

        Returns:
            Either a list of RetrievedChunk objects OR a SearchResult object.

            RetrievedChunk contains:
            - content: The actual text content
            - score: Relevance score (if available, otherwise None)
            - metadata: Tool-specific metadata (doc_id, chunk_id, source, etc.)

            SearchResult wraps chunks and adds:
            - cost: Execution cost (if available)
            - metadata: Additional execution metadata

        Raises:
            RunError: If search fails (API error, timeout, network issue, etc.)

        Example:
            >>> chunks = provider.search("What is Islamic law?", top_k=3)
            >>> chunks[0].content
            'Islamic law, also known as Sharia...'
            >>> chunks[0].score
            0.95
            >>> chunks[0].metadata
            {'doc_id': 'quran_1', 'chapter': 4, 'verse': 12}
        """
        pass

    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}()"
