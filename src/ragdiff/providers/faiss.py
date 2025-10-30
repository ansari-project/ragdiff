"""FAISS provider for RAGDiff v2.0.

A local vector similarity search provider using FAISS (Facebook AI Similarity Search).
Supports multiple embedding services including sentence-transformers, OpenAI, and Anthropic.

Configuration:
    index_path: Path to FAISS index file (string, required)
    documents_path: Path to JSONL documents file (string, required)
    embedding_service: Embedding service ("sentence-transformers", "openai", "anthropic", default: "sentence-transformers")
    embedding_model: Model name (string, default: "all-MiniLM-L6-v2")
    dimensions: Expected vector dimensions for validation (int, optional)
    api_key: API key for OpenAI/Anthropic (string, optional - from env var)

Example:
    >>> provider = FAISSProvider(config={
    ...     "index_path": "/path/to/index.faiss",
    ...     "documents_path": "/path/to/docs.jsonl",
    ...     "embedding_service": "sentence-transformers",
    ...     "embedding_model": "all-MiniLM-L6-v2"
    ... })
    >>> chunks = provider.search("What is FAISS?", top_k=5)
"""

import json
from pathlib import Path
from typing import Any

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import RetrievedChunk
from .abc import Provider

logger = get_logger(__name__)


class FAISSProvider(Provider):
    """FAISS local vector similarity search provider.

    Uses FAISS for efficient similarity search over document embeddings.
    Documents are stored in JSONL format with structure:
    {"id": "...", "text": "...", "source": "...", "metadata": {...}}
    """

    def __init__(self, config: dict):
        """Initialize FAISS provider.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigError: If required config missing or invalid
        """
        super().__init__(config)

        # Validate required fields
        required = ["index_path", "documents_path"]
        for field in required:
            if field not in config:
                raise ConfigError(f"FAISS provider requires '{field}' in config")

        self.index_path = Path(config["index_path"])
        self.documents_path = Path(config["documents_path"])
        self.embedding_service = config.get(
            "embedding_service", "sentence-transformers"
        )
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.dimensions = config.get("dimensions")
        self.api_key = config.get("api_key")  # For OpenAI/Anthropic

        # Initialize embedding service
        self._init_embedding_service()

        # Load FAISS index
        self._load_index()

        # Load documents
        self._load_documents()

        logger.debug(
            f"Initialized FAISS provider: {len(self.documents)} docs, "
            f"embedding={self.embedding_service}/{self.embedding_model}"
        )

    def _init_embedding_service(self) -> None:
        """Initialize the embedding service based on configuration.

        Raises:
            ConfigError: If embedding service setup fails
        """
        if self.embedding_service == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer

                self.encoder = SentenceTransformer(self.embedding_model)
                logger.info(
                    f"Initialized sentence-transformers model: {self.embedding_model}"
                )
            except ImportError as e:
                raise ConfigError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                ) from e
            except Exception as e:
                raise ConfigError(
                    f"Failed to load sentence-transformers model '{self.embedding_model}': {e}"
                ) from e

        elif self.embedding_service == "openai":
            if not self.api_key:
                raise ConfigError("OpenAI embedding service requires api_key in config")

            try:
                import openai

                self.openai_client = openai.OpenAI(api_key=self.api_key)
                self.encoder = None  # We'll use the API directly
                logger.info(
                    f"Initialized OpenAI embeddings with model: {self.embedding_model}"
                )
            except ImportError as e:
                raise ConfigError(
                    "openai not installed. Install with: pip install openai"
                ) from e

        elif self.embedding_service == "anthropic":
            raise ConfigError(
                "Anthropic embeddings not yet available. "
                "Use 'sentence-transformers' or 'openai' instead."
            )

        else:
            raise ConfigError(
                f"Unknown embedding service: {self.embedding_service}. "
                "Supported: sentence-transformers, openai"
            )

    def _load_index(self) -> None:
        """Load FAISS index from disk.

        Raises:
            ConfigError: If index cannot be loaded
        """
        if not self.index_path.exists():
            raise ConfigError(f"FAISS index not found at: {self.index_path}")

        try:
            import faiss

            self.index = faiss.read_index(str(self.index_path))
            logger.info(
                f"Loaded FAISS index with {self.index.ntotal} vectors from {self.index_path}"
            )

            # Validate dimensions if specified
            if self.dimensions is not None and self.index.d != self.dimensions:
                raise ConfigError(
                    f"Index dimension mismatch: expected {self.dimensions}, got {self.index.d}"
                )

        except ImportError as e:
            raise ConfigError(
                "faiss not installed. Install with: pip install faiss-cpu or faiss-gpu"
            ) from e
        except Exception as e:
            raise ConfigError(f"Failed to load FAISS index: {e}") from e

    def _load_documents(self) -> None:
        """Load documents from JSONL file.

        Raises:
            ConfigError: If documents cannot be loaded
        """
        if not self.documents_path.exists():
            raise ConfigError(f"Documents file not found at: {self.documents_path}")

        try:
            self.documents = []
            with open(self.documents_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        doc = json.loads(line.strip())
                        # Validate document structure
                        if "id" not in doc or "text" not in doc:
                            logger.warning(
                                f"Line {line_num}: Document missing 'id' or 'text' field, skipping"
                            )
                            continue
                        self.documents.append(doc)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Line {line_num}: Invalid JSON, skipping: {e}")
                        continue

            logger.info(
                f"Loaded {len(self.documents)} documents from {self.documents_path}"
            )

            # Validate document count matches index
            if len(self.documents) != self.index.ntotal:
                logger.warning(
                    f"Document count ({len(self.documents)}) does not match "
                    f"index size ({self.index.ntotal}). Results may be incorrect."
                )

        except Exception as e:
            raise ConfigError(f"Failed to load documents: {e}") from e

    def _encode_query(self, query: str) -> Any:
        """Encode query text to embedding vector.

        Args:
            query: Query text

        Returns:
            Embedding vector as numpy array

        Raises:
            RunError: If encoding fails
        """
        try:
            if self.embedding_service == "sentence-transformers":
                # Local encoding
                import numpy as np

                embedding = self.encoder.encode([query])[0]
                return np.array(embedding, dtype="float32")

            elif self.embedding_service == "openai":
                # OpenAI API
                import numpy as np

                response = self.openai_client.embeddings.create(
                    input=query, model=self.embedding_model
                )
                embedding = response.data[0].embedding
                return np.array(embedding, dtype="float32")

            else:
                raise RunError(
                    f"Unsupported embedding service: {self.embedding_service}"
                )

        except Exception as e:
            logger.error(f"Failed to encode query: {e}")
            raise RunError(f"Query encoding failed: {e}") from e

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search FAISS index for relevant documents.

        Args:
            query: Search query text
            top_k: Maximum results to return

        Returns:
            List of RetrievedChunk objects

        Raises:
            RunError: If search fails
        """
        try:
            # Encode query
            query_vector = self._encode_query(query)

            # Ensure query vector is 2D for FAISS
            query_vector = query_vector.reshape(1, -1)

            # Search index
            distances, indices = self.index.search(query_vector, top_k)

            # Convert to results
            chunks = []
            for distance, idx in zip(distances[0], indices[0]):
                # Skip invalid indices
                if idx < 0 or idx >= len(self.documents):
                    logger.warning(f"Invalid index {idx}, skipping")
                    continue

                doc = self.documents[idx]

                # Convert distance to similarity score (0-1)
                # For L2 distance, smaller is better, so invert
                # Normalize using sigmoid-like function
                score = 1.0 / (1.0 + float(distance))

                chunk = RetrievedChunk(
                    content=doc["text"],
                    score=score,
                    metadata={
                        "id": str(doc["id"]),
                        "source": doc.get("source", "FAISS"),
                        **(doc.get("metadata", {})),
                        "faiss_distance": float(distance),
                        "faiss_index": int(idx),
                    },
                )
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            raise RunError(f"FAISS search failed: {e}") from e


# Register the provider
from .registry import register_tool  # noqa: E402

register_tool("faiss", FAISSProvider)
