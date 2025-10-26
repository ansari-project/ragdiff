"""Agentset system for RAGDiff v2.0.

Agentset is a RAG-as-a-Service platform. This system uses the Agentset SDK
to perform semantic search over documents stored in an Agentset namespace.

Configuration:
    api_token: Agentset API token (string, required)
    namespace_id: Agentset namespace ID (string, required)
    rerank: Whether to rerank results (bool, optional, default: True)
    timeout: Request timeout in seconds (int, optional, default: 60)

Example:
    >>> system = AgentsetSystem(config={
    ...     "api_token": "agentset_token_...",
    ...     "namespace_id": "ns_abc123",
    ...     "rerank": True
    ... })
    >>> chunks = system.search("What is Islamic law?", top_k=5)
"""

from typing import Any

from agentset import Agentset
from agentset.models.searchop import SearchData

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models_v2 import RetrievedChunk
from .abc import System

logger = get_logger(__name__)


class AgentsetSystem(System):
    """Agentset RAG system implementation.

    Uses the Agentset SDK for semantic search over documents stored in
    an Agentset namespace.

    Requires: agentset (install with: pip install agentset)
    """

    def __init__(self, config: dict):
        """Initialize Agentset system.

        Args:
            config: Configuration dictionary with:
                - api_token (str, required): Agentset API token
                - namespace_id (str, required): Agentset namespace ID
                - rerank (bool, optional): Whether to rerank results
                - timeout (int, optional): Timeout in seconds

        Raises:
            ConfigError: If required config missing or initialization fails
        """
        super().__init__(config)

        # Validate required fields
        if "api_token" not in config:
            raise ConfigError("Agentset config missing required field: api_token")
        if "namespace_id" not in config:
            raise ConfigError("Agentset config missing required field: namespace_id")

        # Store configuration
        self.api_token = config["api_token"]
        self.namespace_id = config["namespace_id"]
        self.rerank = config.get("rerank", True)
        self.timeout = config.get("timeout", 60)

        # Initialize Agentset client
        try:
            self.client = Agentset(
                token=self.api_token,
                namespace_id=self.namespace_id
            )
            logger.info(f"Agentset client initialized for namespace: {self.namespace_id}")
        except Exception as e:
            raise ConfigError(f"Failed to initialize Agentset client: {e}") from e

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search Agentset namespace for relevant documents.

        Args:
            query: Search query text
            top_k: Maximum number of results to return

        Returns:
            List of RetrievedChunk objects with content, score, and metadata

        Raises:
            RunError: If search fails
        """
        try:
            logger.debug(f"Agentset search: query='{query[:50]}...', top_k={top_k}")

            # Execute search using Agentset SDK
            # Note: include_metadata=False to avoid SDK validation errors
            search_response = self.client.search.execute(
                query=query,
                top_k=float(top_k),  # Agentset expects float
                include_metadata=False,  # Avoid strict validation errors
                mode="semantic",  # Use semantic search by default
            )

            # Extract data from response
            if hasattr(search_response, "data") and isinstance(search_response.data, list):
                search_results: list[SearchData] = search_response.data
            else:
                search_results = []

            logger.info(
                f"Agentset returned {len(search_results)} results for query: '{query[:50]}...'"
            )

            # Convert SearchData objects to RetrievedChunk format
            chunks = []
            for idx, search_data in enumerate(search_results):
                # Extract text content
                text = search_data.text or ""
                if not text:
                    logger.warning(f"Skipping result {idx}: no text content")
                    continue

                # Extract score
                score = search_data.score or 0.0

                # Build metadata dictionary
                metadata: dict[str, Any] = {
                    "document_id": search_data.id,
                }

                # Add metadata from Agentset response
                if search_data.metadata:
                    metadata["filename"] = search_data.metadata.filename
                    metadata["filetype"] = search_data.metadata.filetype
                    metadata["file_directory"] = search_data.metadata.file_directory

                    # Add optional metadata fields if present
                    if search_data.metadata.sequence_number is not None:
                        metadata["sequence_number"] = str(search_data.metadata.sequence_number)
                    if search_data.metadata.languages:
                        metadata["languages"] = (
                            search_data.metadata.languages
                            if isinstance(search_data.metadata.languages, str)
                            else str(search_data.metadata.languages)
                        )

                # Create chunk
                chunk = RetrievedChunk(
                    content=text,
                    score=score,
                    metadata=metadata
                )
                chunks.append(chunk)

            logger.info(f"Converted {len(chunks)} Agentset results to RetrievedChunk format")
            return chunks

        except Exception as e:
            logger.error(f"Agentset search failed: {e}")
            raise RunError(f"Agentset search failed: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"AgentsetSystem(namespace_id='{self.namespace_id}')"


# Register the tool
from .registry import register_tool

register_tool("agentset", AgentsetSystem)
