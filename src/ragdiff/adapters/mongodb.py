"""MongoDB Vector Search adapter for RAG search.

This adapter connects to MongoDB (local or Atlas) and uses vector similarity search
for semantic retrieval. Uses sentence-transformers for local embedding generation.

Features:
- Vector similarity search using MongoDB
- Local embedding generation with sentence-transformers
- Configurable vector index and field mappings
- Metadata filtering and extraction
"""

import logging
import os
from typing import Any

from ..core.errors import AdapterError, ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

logger = logging.getLogger(__name__)

# Conditional imports for optional dependencies
try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.warning("pymongo not installed. Install with: pip install pymongo")

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. Install with: pip install sentence-transformers"
    )


class MongoDBAdapter(RagAdapter):
    """Adapter for MongoDB Vector Search.

    Supports semantic search using vector similarity in MongoDB.
    Uses sentence-transformers for local, free embedding generation.
    """

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "mongodb"

    def __init__(self, config: ToolConfig, credentials: dict[str, str] | None = None):
        """Initialize MongoDB adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides

        Raises:
            ConfigurationError: If required dependencies or configuration are missing
        """
        super().__init__(config, credentials)
        self.validate_config(config.__dict__)

        # Check for required dependencies
        if not PYMONGO_AVAILABLE:
            raise ConfigurationError(
                "pymongo is required for MongoDB adapter. Install with: pip install pymongo"
            )

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ConfigurationError(
                "sentence-transformers is required for MongoDB adapter. "
                "Install with: pip install sentence-transformers"
            )

        # Get MongoDB connection credentials
        connection_uri = self._get_credential(config.api_key_env)
        if not connection_uri:
            raise ConfigurationError(
                f"Missing MongoDB connection URI: {config.api_key_env}"
            )

        # Parse options from config
        options = config.options or {}

        # Required configuration
        self.database_name = options.get("database")
        self.collection_name = options.get("collection")
        self.index_name = options.get("index_name")

        if not self.database_name:
            raise ConfigurationError("MongoDB adapter requires 'database' in options")
        if not self.collection_name:
            raise ConfigurationError("MongoDB adapter requires 'collection' in options")
        if not self.index_name:
            raise ConfigurationError(
                "MongoDB adapter requires 'index_name' in options"
            )

        # Optional configuration with defaults
        self.vector_field = options.get("vector_field", "embedding")
        self.text_field = options.get("text_field", "text")
        self.source_field = options.get("source_field", "source")
        self.metadata_fields = options.get("metadata_fields", [])

        # Embedding configuration
        self.embedding_model_name = options.get(
            "embedding_model", "all-MiniLM-L6-v2"
        )

        # Initialize sentence-transformers model
        logger.info(f"Loading embedding model: {self.embedding_model_name}")
        try:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Embedding model loaded successfully")
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load embedding model '{self.embedding_model_name}': {e}"
            ) from e

        # Initialize MongoDB client
        try:
            self.mongo_client = MongoClient(connection_uri)
            self.database = self.mongo_client[self.database_name]
            self.collection = self.database[self.collection_name]

            # Test connection
            self.mongo_client.admin.command("ping")
            logger.info(
                f"MongoDB client initialized for database: {self.database_name}, "
                f"collection: {self.collection_name}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB client: {e}")
            raise ConfigurationError(
                f"Failed to connect to MongoDB: {e}"
            ) from e

        # Store basic configuration
        self.name = config.name
        self.timeout = config.timeout or 60
        self.default_top_k = config.default_top_k or 5
        self.description = "MongoDB Vector Search with sentence-transformers"

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search MongoDB using vector similarity.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects

        Raises:
            AdapterError: If search fails
        """
        try:
            # Generate embedding for query
            query_vector = self._generate_embedding(query)

            # For MongoDB Community Edition, we need to use basic similarity search
            # since $vectorSearch requires Atlas
            # We'll use a simple approach: fetch all docs and compute cosine similarity
            logger.info(f"Performing vector similarity search in MongoDB")

            # Fetch all documents with embeddings
            all_docs = list(self.collection.find({self.vector_field: {"$exists": True}}))

            if not all_docs:
                logger.warning("No documents with embeddings found in collection")
                return []

            # Compute cosine similarity for each document
            import numpy as np

            results_with_scores = []
            for doc in all_docs:
                doc_vector = np.array(doc.get(self.vector_field, []))
                if len(doc_vector) == 0:
                    continue

                # Cosine similarity
                similarity = np.dot(query_vector, doc_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                )

                results_with_scores.append((doc, float(similarity)))

            # Sort by similarity (descending) and take top_k
            results_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_results = results_with_scores[:top_k]

            # Convert to RagResult objects
            rag_results = []
            for i, (doc, score) in enumerate(top_results):
                # Extract text
                text = doc.get(self.text_field, "")
                if not text:
                    logger.warning(f"Document missing text field: {doc.get('_id')}")
                    continue

                # Extract source
                source = doc.get(self.source_field, "MongoDB")

                # Build metadata
                metadata = {"_id": str(doc.get("_id", ""))}
                for field in self.metadata_fields:
                    if field in doc:
                        metadata[field] = doc[field]

                # Create RagResult
                result = RagResult(
                    id=str(doc.get("_id", f"mongodb_{i}")),
                    text=text,
                    score=score,  # Cosine similarity is already 0-1
                    source=source,
                    metadata=metadata,
                )
                rag_results.append(result)

            logger.info(f"MongoDB returned {len(rag_results)} results")
            return rag_results

        except PyMongoError as e:
            logger.error(f"MongoDB query failed: {str(e)}")
            raise AdapterError(f"MongoDB query failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error in MongoDB search: {str(e)}")
            raise AdapterError(f"Unexpected error in MongoDB search: {str(e)}") from e

    def _generate_embedding(self, text: str) -> Any:
        """Generate embedding vector for text using sentence-transformers.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array

        Raises:
            AdapterError: If embedding generation fails
        """
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise AdapterError(f"Failed to generate embedding: {str(e)}") from e

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate MongoDB configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check required fields
        if not config.get("api_key_env"):
            raise ConfigurationError(
                "MongoDB config missing required field: api_key_env"
            )

        # Check required options
        options = config.get("options", {})
        required_options = ["database", "collection", "index_name"]

        for opt in required_options:
            if not options.get(opt):
                raise ConfigurationError(
                    f"MongoDB config missing required option: {opt}"
                )

        # Validate environment variable exists
        if not os.getenv(config["api_key_env"]):
            raise ConfigurationError(
                f"Environment variable {config['api_key_env']} is not set"
            )

    def get_required_env_vars(self) -> list[str]:
        """Get list of required environment variables.

        Returns:
            List of required environment variable names
        """
        return [self.config.api_key_env]

    def get_options_schema(self) -> dict[str, Any]:
        """Get JSON schema for MongoDB configuration options.

        Returns:
            JSON schema for configuration options
        """
        return {
            "type": "object",
            "properties": {
                "database": {
                    "type": "string",
                    "description": "MongoDB database name",
                },
                "collection": {
                    "type": "string",
                    "description": "MongoDB collection name",
                },
                "index_name": {
                    "type": "string",
                    "description": "Vector search index name",
                },
                "vector_field": {
                    "type": "string",
                    "description": "Field containing vector embeddings",
                    "default": "embedding",
                },
                "text_field": {
                    "type": "string",
                    "description": "Field containing text content",
                    "default": "text",
                },
                "source_field": {
                    "type": "string",
                    "description": "Field containing source information",
                    "default": "source",
                },
                "metadata_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional metadata fields to include in results",
                    "default": [],
                },
                "embedding_model": {
                    "type": "string",
                    "description": "Sentence-transformer model name",
                    "default": "all-MiniLM-L6-v2",
                },
            },
            "required": ["database", "collection", "index_name"],
        }

    def __del__(self):
        """Clean up MongoDB connection."""
        if hasattr(self, "mongo_client"):
            try:
                self.mongo_client.close()
                logger.debug("MongoDB connection closed")
            except Exception as e:
                logger.debug(f"Error closing MongoDB connection: {e}")


# Register adapter on import
from .registry import register_adapter

register_adapter(MongoDBAdapter)
