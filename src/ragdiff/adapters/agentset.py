"""Agentset adapter for RAG search."""

import logging
import os
from typing import List

from agentset import Agentset
from agentset.models.searchop import SearchData

from ..core.models import RagResult, ToolConfig
from .base import BaseRagTool

logger = logging.getLogger(__name__)


class AgentsetAdapter(BaseRagTool):
    """Adapter for Agentset RAG-as-a-Service platform."""

    def __init__(self, config: ToolConfig):
        """Initialize Agentset adapter.

        Args:
            config: Tool configuration

        Raises:
            ValueError: If required environment variables are missing
        """
        # Store config before super().__init__ because we need custom credential handling
        self.config = config

        # Get API credentials from environment
        api_token = os.getenv(config.api_key_env)
        if not api_token:
            raise ValueError(
                f"Missing required environment variable: {config.api_key_env}\n"
                f"Please set it with your Agentset API token."
            )

        # Get namespace ID - check for custom env var name or default
        namespace_id_env = getattr(config, "namespace_id_env", "AGENTSET_NAMESPACE_ID")
        namespace_id = os.getenv(namespace_id_env)
        if not namespace_id:
            raise ValueError(
                f"Missing required environment variable: {namespace_id_env}\n"
                f"Please set it with your Agentset namespace ID."
            )

        # Initialize Agentset client
        try:
            self.client = Agentset(token=api_token, namespace_id=namespace_id)
            logger.info(f"Agentset client initialized for namespace: {namespace_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Agentset client: {e}")
            raise ValueError(f"Failed to initialize Agentset client: {e}")

        # Set config attributes needed by BaseRagTool
        self.name = config.name
        self.timeout = config.timeout
        self.max_retries = config.max_retries
        self.default_top_k = config.default_top_k

        # Note: We don't call super().__init__ because Agentset doesn't use
        # the Vectara-compatible parameters (api_key, corpus_id, etc.)
        # Instead we set the attributes directly
        self.description = "Agentset RAG-as-a-Service platform"

        # Store credentials for BaseRagTool compatibility
        self.api_key = api_token
        self.corpus_id = namespace_id  # Use namespace as corpus equivalent
        self.base_url = getattr(config, "base_url", None)
        self.customer_id = None  # Not used by Agentset

        # Parse adapter-specific options
        self.rerank = True  # Default to True
        if config.options:
            self.rerank = config.options.get("rerank", True)
            logger.info(f"Agentset rerank option set to: {self.rerank}")

    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        """Search Agentset for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects

        Raises:
            Exception: If search fails
        """
        try:
            # Execute search using Agentset SDK
            # The SDK returns SearchResponse with .data containing List[SearchData]
            # Note: include_metadata=False to avoid SDK validation errors
            # The SDK expects all metadata fields but Agentset API returns partial metadata

            # TODO: Add rerank parameter once Agentset SDK support is verified
            # If supported, add: rerank=self.rerank to the execute() call below
            search_response = self.client.search.execute(
                query=query,
                top_k=float(top_k),  # Agentset expects float
                include_metadata=False,  # Avoid strict validation errors
                mode="semantic",  # Use semantic search by default
            )

            # Extract data from response
            search_results: List[SearchData] = search_response.data
            logger.info(
                f"Agentset returned {len(search_results)} results for query: {query}"
            )

            # Convert SearchData objects to RagResult format
            results = []
            for idx, search_data in enumerate(search_results):
                # Extract text content
                text = search_data.text or ""
                if not text:
                    logger.warning(f"Skipping result {idx}: no text content")
                    continue

                # Extract score
                score = search_data.score or 0.0

                # Build source from metadata
                source = "Agentset"
                metadata_dict = {}

                if search_data.metadata:
                    # Extract filename as source
                    source = search_data.metadata.filename or "Agentset"

                    # Build metadata dictionary
                    metadata_dict = {
                        "filename": search_data.metadata.filename,
                        "filetype": search_data.metadata.filetype,
                        "file_directory": search_data.metadata.file_directory,
                    }

                    # Add optional metadata fields if present
                    if search_data.metadata.sequence_number is not None:
                        metadata_dict["sequence_number"] = (
                            search_data.metadata.sequence_number
                        )
                    if search_data.metadata.languages:
                        metadata_dict["languages"] = search_data.metadata.languages

                # Add document ID to metadata
                metadata_dict["document_id"] = search_data.id

                # Create RagResult
                result = RagResult(
                    id=search_data.id,
                    text=text,
                    score=self._normalize_score(score),
                    source=source,
                    metadata=metadata_dict,
                )
                results.append(result)

            logger.info(
                f"Converted {len(results)} Agentset results to RagResult format"
            )
            return results

        except Exception as e:
            logger.error(f"Agentset search failed: {str(e)}")
            raise
