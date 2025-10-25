"""FAISS adapter for local vector similarity search.

This adapter uses FAISS (Facebook AI Similarity Search) for efficient
similarity search over document embeddings. It supports multiple embedding
services including sentence-transformers (local), OpenAI, and Anthropic.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from ..core.errors import AdapterError, ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

logger = logging.getLogger(__name__)


class FaissAdapter(RagAdapter):
    """Adapter for FAISS local vector similarity search.

    Supports multiple embedding services for query encoding:
    - sentence-transformers: Local models, no API key needed
    - openai: OpenAI embeddings API
    - anthropic: Anthropic embeddings (when available)

    Documents are stored in JSONL format with structure:
    {"id": "...", "text": "...", "source": "...", "metadata": {...}}
    """

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "faiss"

    def __init__(self, config: ToolConfig, credentials: dict[str, str] | None = None):
        """Initialize FAISS adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides
        """
        super().__init__(config, credentials)
        self.validate_config(config.__dict__)

        # Get configuration
        self.index_path = Path(config.options.get("index_path"))
        self.documents_path = Path(config.options.get("documents_path"))
        self.embedding_service = config.options.get(
            "embedding_service", "sentence-transformers"
        )
        self.embedding_model = config.options.get(
            "embedding_model", "all-MiniLM-L6-v2"
        )
        self.dimensions = config.options.get("dimensions")
        self.timeout = config.timeout or 60
        self.default_top_k = config.default_top_k or 5
        self.name = config.name
        self.description = "FAISS local vector search"

        # Initialize embedding service
        self._init_embedding_service(config)

        # Load FAISS index
        self._load_index()

        # Load documents
        self._load_documents()

    def _init_embedding_service(self, config: ToolConfig) -> None:
        """Initialize the embedding service based on configuration.

        Args:
            config: Tool configuration

        Raises:
            ConfigurationError: If embedding service setup fails
        """
        if self.embedding_service == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer

                self.encoder = SentenceTransformer(self.embedding_model)
                logger.info(
                    f"Initialized sentence-transformers model: {self.embedding_model}"
                )
            except ImportError:
                raise ConfigurationError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to load sentence-transformers model '{self.embedding_model}': {e}"
                )

        elif self.embedding_service == "openai":
            # Get API key
            api_key = self._get_credential(config.api_key_env)
            if not api_key:
                raise ConfigurationError(
                    f"Missing OpenAI API key environment variable: {config.api_key_env}"
                )

            try:
                import openai

                self.openai_client = openai.OpenAI(api_key=api_key)
                self.encoder = None  # We'll use the API directly
                logger.info(f"Initialized OpenAI embeddings with model: {self.embedding_model}")
            except ImportError:
                raise ConfigurationError(
                    "openai not installed. Install with: pip install openai"
                )

        elif self.embedding_service == "anthropic":
            raise ConfigurationError(
                "Anthropic embeddings not yet available. "
                "Use 'sentence-transformers' or 'openai' instead."
            )

        else:
            raise ConfigurationError(
                f"Unknown embedding service: {self.embedding_service}. "
                "Supported: sentence-transformers, openai"
            )

    def _load_index(self) -> None:
        """Load FAISS index from disk.

        Raises:
            ConfigurationError: If index cannot be loaded
        """
        if not self.index_path.exists():
            raise ConfigurationError(
                f"FAISS index not found at: {self.index_path}"
            )

        try:
            import faiss

            self.index = faiss.read_index(str(self.index_path))
            logger.info(
                f"Loaded FAISS index with {self.index.ntotal} vectors from {self.index_path}"
            )

            # Validate dimensions if specified
            if self.dimensions is not None and self.index.d != self.dimensions:
                raise ConfigurationError(
                    f"Index dimension mismatch: expected {self.dimensions}, "
                    f"got {self.index.d}"
                )

        except ImportError:
            raise ConfigurationError(
                "faiss not installed. Install with: pip install faiss-cpu or faiss-gpu"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load FAISS index: {e}")

    def _load_documents(self) -> None:
        """Load documents from JSONL file.

        Raises:
            ConfigurationError: If documents cannot be loaded
        """
        if not self.documents_path.exists():
            raise ConfigurationError(
                f"Documents file not found at: {self.documents_path}"
            )

        try:
            self.documents = []
            with open(self.documents_path, "r", encoding="utf-8") as f:
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
            raise ConfigurationError(f"Failed to load documents: {e}")

    def _encode_query(self, query: str) -> "np.ndarray":
        """Encode query text to embedding vector.

        Args:
            query: Query text

        Returns:
            Embedding vector as numpy array

        Raises:
            AdapterError: If encoding fails
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
                raise AdapterError(f"Unsupported embedding service: {self.embedding_service}")

        except Exception as e:
            logger.error(f"Failed to encode query: {e}")
            raise AdapterError(f"Query encoding failed: {e}") from e

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search FAISS index for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        try:
            import numpy as np

            # Encode query
            query_vector = self._encode_query(query)

            # Ensure query vector is 2D for FAISS
            query_vector = query_vector.reshape(1, -1)

            # Search index
            distances, indices = self.index.search(query_vector, top_k)

            # Convert to results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                # Skip invalid indices
                if idx < 0 or idx >= len(self.documents):
                    logger.warning(f"Invalid index {idx}, skipping")
                    continue

                doc = self.documents[idx]

                # Convert distance to similarity score (0-1)
                # For L2 distance, smaller is better, so invert
                # Normalize using sigmoid-like function
                score = 1.0 / (1.0 + float(distance))

                result = RagResult(
                    id=str(doc["id"]),
                    text=doc["text"],
                    score=score,
                    source=doc.get("source", "FAISS"),
                    metadata={
                        **(doc.get("metadata", {})),
                        "faiss_distance": float(distance),
                        "faiss_index": int(idx),
                    },
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            raise AdapterError(f"FAISS search failed: {e}") from e

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate FAISS configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check required fields
        if not config.get("api_key_env"):
            raise ConfigurationError(
                "FAISS config missing required field: api_key_env"
            )

        # Check options
        options = config.get("options", {})
        if not options:
            raise ConfigurationError("FAISS config missing 'options' field")

        if not options.get("index_path"):
            raise ConfigurationError(
                "FAISS config missing required option: index_path"
            )

        if not options.get("documents_path"):
            raise ConfigurationError(
                "FAISS config missing required option: documents_path"
            )

        # Validate embedding service
        embedding_service = options.get("embedding_service", "sentence-transformers")
        if embedding_service not in ["sentence-transformers", "openai", "anthropic"]:
            raise ConfigurationError(
                f"Invalid embedding service: {embedding_service}. "
                "Supported: sentence-transformers, openai, anthropic"
            )

        # Validate API key for services that need it
        if embedding_service in ["openai", "anthropic"]:
            api_key_env = config.get("api_key_env")
            if not os.getenv(api_key_env):
                raise ConfigurationError(
                    f"Environment variable {api_key_env} is not set "
                    f"(required for {embedding_service})"
                )

    def get_required_env_vars(self) -> list[str]:
        """Get list of required environment variables.

        Returns:
            List of required environment variable names
        """
        # Only required if using OpenAI or Anthropic
        if self.embedding_service in ["openai", "anthropic"]:
            return [self.config.api_key_env]
        return []

    def get_options_schema(self) -> dict[str, Any]:
        """Get JSON schema for FAISS configuration options.

        Returns:
            JSON schema for configuration options
        """
        return {
            "type": "object",
            "properties": {
                "index_path": {
                    "type": "string",
                    "description": "Path to FAISS index file",
                },
                "documents_path": {
                    "type": "string",
                    "description": "Path to JSONL documents file",
                },
                "embedding_service": {
                    "type": "string",
                    "description": "Embedding service to use",
                    "enum": ["sentence-transformers", "openai", "anthropic"],
                    "default": "sentence-transformers",
                },
                "embedding_model": {
                    "type": "string",
                    "description": "Embedding model name",
                    "default": "all-MiniLM-L6-v2",
                },
                "dimensions": {
                    "type": "integer",
                    "description": "Expected vector dimensions (for validation)",
                    "minimum": 1,
                },
            },
            "required": ["index_path", "documents_path"],
        }


# Register adapter on import
from .registry import register_adapter

register_adapter(FaissAdapter)
