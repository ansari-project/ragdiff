"""System abstract base class for RAGDiff v2.0.

A System is a RAG tool (like Vectara, MongoDB, Agentset) configured with
specific settings. Systems implement a simple interface: search(query, top_k).

Example:
    >>> system = VectaraSystem(config={
    ...     "api_key": "...",
    ...     "corpus_id": 123,
    ... })
    >>> chunks = system.search("What is Islamic law?", top_k=5)
    >>> for chunk in chunks:
    ...     print(f"Score: {chunk.score}, Content: {chunk.content[:100]}")
"""

from abc import ABC, abstractmethod

from ..core.models_v2 import RetrievedChunk


class System(ABC):
    """Abstract base class for all RAG systems.

    A System wraps a RAG tool (Vectara, MongoDB, Agentset, etc.) with specific
    configuration. All systems must implement the search() method.

    Systems are instantiated from SystemConfig objects and registered in the
    TOOL_REGISTRY for discovery.

    Thread Safety:
        Systems must be thread-safe for parallel query execution. If your
        underlying client is not thread-safe, use locks or create per-query
        clients.

    Attributes:
        config: Dictionary of tool-specific configuration (API keys, endpoints, etc.)

    Example:
        class MySystem(System):
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
        """Initialize the system with configuration.

        Args:
            config: Tool-specific configuration dictionary (API keys, endpoints, etc.)

        Raises:
            ConfigError: If required configuration is missing or invalid
        """
        self.config = config

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search and return ranked chunks with metadata.

        Args:
            query: The search query text
            top_k: Maximum number of results to return (default: 5)

        Returns:
            List of RetrievedChunk objects, ordered by relevance (highest first).
            Each chunk contains:
            - content: The actual text content
            - score: Relevance score (if available, otherwise None)
            - metadata: Tool-specific metadata (doc_id, chunk_id, source, etc.)

        Raises:
            RunError: If search fails (API error, timeout, network issue, etc.)

        Example:
            >>> chunks = system.search("What is Islamic law?", top_k=3)
            >>> chunks[0].content
            'Islamic law, also known as Sharia...'
            >>> chunks[0].score
            0.95
            >>> chunks[0].metadata
            {'doc_id': 'quran_1', 'chapter': 4, 'verse': 12}
        """
        pass

    def __repr__(self) -> str:
        """String representation of the system."""
        return f"{self.__class__.__name__}()"
