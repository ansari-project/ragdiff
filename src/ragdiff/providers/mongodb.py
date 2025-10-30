"""MongoDB system for RAGDiff v2.0.

MongoDB vector search using sentence-transformers for local embedding generation.
Requires optional dependencies: pymongo, sentence-transformers.

Configuration:
    connection_uri: MongoDB connection string (string, required)
    database: Database name (string, required)
    collection: Collection name (string, required)
    index_name: Vector index name (string, required)
    vector_field: Vector field name (string, optional, default: "embedding")
    text_field: Text field name (string, optional, default: "text")
    source_field: Source field name (string, optional, default: "source")
    metadata_fields: List of metadata fields to extract (list, optional)
    embedding_model: Sentence-transformer model name (string, optional, default: "all-MiniLM-L6-v2")
    timeout: Request timeout in seconds (int, optional, default: 60)

Example:
    >>> system = MongoDBProvider(config={
    ...     "connection_uri": "mongodb://localhost:27017",
    ...     "database": "tafsir",
    ...     "collection": "documents",
    ...     "index_name": "vector_index",
    ...     "embedding_model": "all-MiniLM-L6-v2"
    ... })
    >>> chunks = system.search("What is Islamic law?", top_k=5)
"""

from typing import Any

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import RetrievedChunk
from .abc import Provider

logger = get_logger(__name__)


class MongoDBProvider(Provider):
    """MongoDB vector search system implementation.

    Uses sentence-transformers for local embedding generation and MongoDB
    for vector similarity search.

    Requires: pymongo, sentence-transformers (install with: pip install pymongo sentence-transformers)
    """

    def __init__(self, config: dict):
        """Initialize MongoDB system.

        Args:
            config: Configuration dictionary with:
                - connection_uri (str, required): MongoDB connection string
                - database (str, required): Database name
                - collection (str, required): Collection name
                - index_name (str, required): Vector index name
                - vector_field (str, optional): Vector field name
                - text_field (str, optional): Text field name
                - source_field (str, optional): Source field name
                - metadata_fields (list, optional): Metadata fields to extract
                - embedding_model (str, optional): Sentence-transformer model
                - timeout (int, optional): Timeout in seconds

        Raises:
            ConfigError: If required config missing, invalid, or dependencies not installed
        """
        super().__init__(config)

        # Lazy load dependencies
        try:
            import numpy as np
            from pymongo import MongoClient
            from pymongo.errors import PyMongoError

            self.np = np
            self.MongoClient = MongoClient
            self.PyMongoError = PyMongoError
        except ImportError as e:
            raise ConfigError(
                f"pymongo is required for MongoDB provider. Install with: pip install pymongo. Error: {e}"
            ) from e

        try:
            from sentence_transformers import SentenceTransformer

            self.SentenceTransformer = SentenceTransformer
        except ImportError as e:
            raise ConfigError(
                f"sentence-transformers is required for MongoDB provider. "
                f"Install with: pip install sentence-transformers. Error: {e}"
            ) from e

        # Validate required fields
        if "connection_uri" not in config:
            raise ConfigError("MongoDB config missing required field: connection_uri")
        if "database" not in config:
            raise ConfigError("MongoDB config missing required field: database")
        if "collection" not in config:
            raise ConfigError("MongoDB config missing required field: collection")
        if "index_name" not in config:
            raise ConfigError("MongoDB config missing required field: index_name")

        # Store configuration
        self.database_name = config["database"]
        self.collection_name = config["collection"]
        self.index_name = config["index_name"]
        self.vector_field = config.get("vector_field", "embedding")
        self.text_field = config.get("text_field", "text")
        self.source_field = config.get("source_field", "source")
        self.metadata_fields = config.get("metadata_fields", [])
        self.embedding_model_name = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.timeout = config.get("timeout", 60)

        # Initialize embedding model
        logger.info(f"Loading embedding model: {self.embedding_model_name}")
        try:
            self.embedding_model = self.SentenceTransformer(self.embedding_model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            raise ConfigError(
                f"Failed to load embedding model '{self.embedding_model_name}': {e}"
            ) from e

        # Initialize MongoDB client
        try:
            self.mongo_client = self.MongoClient(
                config["connection_uri"], serverSelectionTimeoutMS=self.timeout * 1000
            )
            self.database = self.mongo_client[self.database_name]
            self.collection = self.database[self.collection_name]

            # Test connection
            self.mongo_client.admin.command("ping")
            logger.info(
                f"MongoDB client initialized for database: {self.database_name}, "
                f"collection: {self.collection_name}"
            )
        except Exception as e:
            raise ConfigError(f"Failed to connect to MongoDB: {e}") from e

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search MongoDB using vector similarity.

        Args:
            query: Search query text
            top_k: Maximum number of results to return

        Returns:
            List of RetrievedChunk objects with content, score, and metadata

        Raises:
            RunError: If search fails
        """
        try:
            # Generate embedding for query
            query_vector = self._generate_embedding(query)

            logger.debug(f"MongoDB search: query='{query[:50]}...', top_k={top_k}")

            # Fetch all documents with embeddings
            # Note: For production with large collections, use MongoDB Atlas $vectorSearch
            # This implementation works for smaller collections
            all_docs = list(
                self.collection.find(
                    {self.vector_field: {"$exists": True}},
                    limit=10000,  # Safety limit
                )
            )

            if not all_docs:
                logger.warning("No documents with embeddings found in collection")
                return []

            # Compute cosine similarity for each document
            results_with_scores = []
            for doc in all_docs:
                doc_vector = self.np.array(doc.get(self.vector_field, []))
                if len(doc_vector) == 0:
                    continue

                # Cosine similarity
                similarity = float(
                    self.np.dot(query_vector, doc_vector)
                    / (
                        self.np.linalg.norm(query_vector)
                        * self.np.linalg.norm(doc_vector)
                    )
                )

                results_with_scores.append((doc, similarity))

            # Sort by similarity (descending) and take top_k
            results_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_results = results_with_scores[:top_k]

            # Convert to RetrievedChunk objects
            chunks = []
            for doc, score in top_results:
                # Extract text
                text = doc.get(self.text_field, "")
                if not text:
                    logger.warning(f"Document missing text field: {doc.get('_id')}")
                    continue

                # Build metadata
                metadata = {
                    "_id": str(doc.get("_id", "")),
                    "source": doc.get(self.source_field, "MongoDB"),
                }

                # Add configured metadata fields
                for field in self.metadata_fields:
                    if field in doc:
                        metadata[field] = doc[field]

                # Create chunk
                chunk = RetrievedChunk(content=text, score=score, metadata=metadata)
                chunks.append(chunk)

            logger.info(
                f"MongoDB returned {len(chunks)} chunks for query: '{query[:50]}...'"
            )
            return chunks

        except self.PyMongoError as e:
            logger.error(f"MongoDB query failed: {e}")
            raise RunError(f"MongoDB query failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in MongoDB search: {e}")
            raise RunError(f"Unexpected error in MongoDB search: {e}") from e

    def _generate_embedding(self, text: str) -> Any:
        """Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array

        Raises:
            RunError: If embedding generation fails
        """
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RunError(f"Failed to generate embedding: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"MongoDBProvider(database='{self.database_name}', collection='{self.collection_name}')"


# Register the tool
from .registry import register_tool

register_tool("mongodb", MongoDBProvider)
