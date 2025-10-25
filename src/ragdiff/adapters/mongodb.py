"""MongoDB Atlas Vector Search adapter for RAG search.

This adapter connects to MongoDB Atlas and uses Vector Search for semantic retrieval.
Requires a pre-configured vector search index in MongoDB Atlas.

Features:
- Vector similarity search using MongoDB Atlas Vector Search
- Support for multiple embedding providers (OpenAI, Cohere, etc.)
- Configurable vector index and field mappings
- Metadata filtering and extraction
"""

import logging
import os
from typing import Any, Optional

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
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai not installed. Install with: pip install openai")


class MongoDBAdapter(RagAdapter):
    """Adapter for MongoDB Atlas Vector Search.

    Supports semantic search using pre-configured vector search indexes
    in MongoDB Atlas. Requires embeddings to be generated using a supported
    embedding provider (OpenAI, Cohere, etc.).
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
        self.num_candidates = options.get("num_candidates", 150)
        self.metadata_fields = options.get("metadata_fields", [])

        # Embedding configuration
        self.embedding_provider = options.get("embedding_provider", "openai")
        self.embedding_model = options.get(
            "embedding_model", "text-embedding-3-small"
        )
        self.embedding_api_key_env = options.get(
            "embedding_api_key_env", "OPENAI_API_KEY"
        )

        # Get embedding API key
        self.embedding_api_key = self._get_credential(self.embedding_api_key_env)
        if not self.embedding_api_key:
            raise ConfigurationError(
                f"Missing embedding API key: {self.embedding_api_key_env}"
            )

        # Initialize embedding client based on provider
        if self.embedding_provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ConfigurationError(
                    "openai package required for OpenAI embeddings. "
                    "Install with: pip install openai"
                )
            self.embedding_client = openai.OpenAI(api_key=self.embedding_api_key)
        else:
            raise ConfigurationError(
                f"Unsupported embedding provider: {self.embedding_provider}. "
                f"Supported providers: openai"
            )

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
        self.description = "MongoDB Atlas Vector Search"

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search MongoDB Atlas using Vector Search.

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

            # Build vector search aggregation pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.index_name,
                        "path": self.vector_field,
                        "queryVector": query_vector,
                        "numCandidates": self.num_candidates,
                        "limit": top_k,
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        self.text_field: 1,
                        self.source_field: 1,
                        "score": {"$meta": "vectorSearchScore"},
                        **{field: 1 for field in self.metadata_fields},
                    }
                },
            ]

            # Execute aggregation pipeline
            logger.info(
                f"Executing MongoDB vector search with index: {self.index_name}"
            )
            results = list(self.collection.aggregate(pipeline))

            # Convert to RagResult objects
            rag_results = []
            for i, doc in enumerate(results):
                # Extract text
                text = doc.get(self.text_field, "")
                if not text:
                    logger.warning(f"Document missing text field: {doc.get('_id')}")
                    continue

                # Extract score
                score = doc.get("score", 0.0)

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
                    score=self._normalize_score(score),
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

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            AdapterError: If embedding generation fails
        """
        try:
            if self.embedding_provider == "openai":
                response = self.embedding_client.embeddings.create(
                    model=self.embedding_model, input=text
                )
                return response.data[0].embedding
            else:
                raise AdapterError(
                    f"Unsupported embedding provider: {self.embedding_provider}"
                )
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise AdapterError(f"Failed to generate embedding: {str(e)}") from e

    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1 range.

        MongoDB Vector Search returns scores in 0-1 range for dotProduct,
        but this method handles other possible scales for consistency.

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

        # Validate environment variables exist
        if not os.getenv(config["api_key_env"]):
            raise ConfigurationError(
                f"Environment variable {config['api_key_env']} is not set"
            )

        # Validate embedding API key environment variable
        embedding_api_key_env = options.get("embedding_api_key_env", "OPENAI_API_KEY")
        if not os.getenv(embedding_api_key_env):
            raise ConfigurationError(
                f"Environment variable {embedding_api_key_env} is not set"
            )

    def get_required_env_vars(self) -> list[str]:
        """Get list of required environment variables.

        Returns:
            List of required environment variable names
        """
        return [self.config.api_key_env, self.embedding_api_key_env]

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
                "num_candidates": {
                    "type": "integer",
                    "description": "Number of candidates for vector search",
                    "minimum": 1,
                    "default": 150,
                },
                "metadata_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional metadata fields to include in results",
                    "default": [],
                },
                "embedding_provider": {
                    "type": "string",
                    "description": "Embedding service provider",
                    "enum": ["openai"],
                    "default": "openai",
                },
                "embedding_model": {
                    "type": "string",
                    "description": "Embedding model name",
                    "default": "text-embedding-3-small",
                },
                "embedding_api_key_env": {
                    "type": "string",
                    "description": "Environment variable for embedding API key",
                    "default": "OPENAI_API_KEY",
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
