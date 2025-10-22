"""Agentset adapter for RAG search."""

import logging
import os
from typing import Any

from agentset import Agentset
from agentset.models.searchop import SearchData

from ..core.errors import AdapterError, ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

logger = logging.getLogger(__name__)


class AgentsetAdapter(RagAdapter):
    """Adapter for Agentset RAG-as-a-Service platform."""

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "agentset"

    def __init__(self, config: ToolConfig, credentials: dict[str, str] | None = None):
        """Initialize Agentset adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides

        Raises:
            ConfigurationError: If required environment variables are missing
        """
        # Store config and validate
        super().__init__(config, credentials)
        self.validate_config(config.__dict__)

        # Get API credentials from override or environment
        api_token = self._get_credential(config.api_key_env)
        if not api_token:
            raise ConfigurationError(
                f"Missing required environment variable: {config.api_key_env}"
            )

        # Get namespace ID - check for custom env var name or default
        # Use 'or' to handle None value from Optional fields
        namespace_id_env = (
            getattr(config, "namespace_id_env", None) or "AGENTSET_NAMESPACE_ID"
        )
        namespace_id = self._get_credential(namespace_id_env)
        if not namespace_id:
            raise ConfigurationError(
                f"Missing required environment variable: {namespace_id_env}"
            )

        # Initialize Agentset client
        try:
            self.client = Agentset(token=api_token, namespace_id=namespace_id)
            logger.info(f"Agentset client initialized for namespace: {namespace_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Agentset client: {e}")
            raise ConfigurationError(
                f"Failed to initialize Agentset client: {e}"
            ) from e

        # Store configuration
        self.name = config.name
        self.timeout = config.timeout or 60
        self.max_retries = config.max_retries or 3
        self.default_top_k = config.default_top_k or 5
        self.description = "Agentset RAG-as-a-Service platform"
        self.api_key = api_token
        self.namespace_id = namespace_id
        self.namespace_id_env = namespace_id_env

        # Parse adapter-specific options
        self.rerank = True  # Default to True
        if config.options:
            self.rerank = config.options.get("rerank", True)
            logger.info(f"Agentset rerank option set to: {self.rerank}")

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
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

            # Extract data from response - the SDK returns a list directly
            if hasattr(search_response, "data") and isinstance(
                search_response.data, list
            ):
                search_results: list[SearchData] = search_response.data
            else:
                search_results = []

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
                metadata_dict: dict[str, Any] = {}

                if search_data.metadata:
                    # Extract filename as source
                    source = search_data.metadata.filename or "Agentset"

                    # Build metadata dictionary with correct types
                    metadata_dict["filename"] = search_data.metadata.filename
                    metadata_dict["filetype"] = search_data.metadata.filetype
                    metadata_dict["file_directory"] = (
                        search_data.metadata.file_directory
                    )

                    # Add optional metadata fields if present
                    if search_data.metadata.sequence_number is not None:
                        metadata_dict["sequence_number"] = str(
                            search_data.metadata.sequence_number
                        )
                    if search_data.metadata.languages:
                        metadata_dict["languages"] = (
                            search_data.metadata.languages
                            if isinstance(search_data.metadata.languages, str)
                            else str(search_data.metadata.languages)
                        )

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
            raise AdapterError(f"Agentset search failed: {str(e)}") from e

    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1 range.

        Agentset returns scores in 0-1 range, but this method handles
        other possible scales for consistency.

        Args:
            score: Raw score

        Returns:
            Normalized score in 0-1 range
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
        """Validate Agentset configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check required fields
        if not config.get("api_key_env"):
            raise ConfigurationError(
                "Agentset config missing required field: api_key_env"
            )

        # Get namespace_id_env (with default)
        # Use 'or' to handle None value from Optional fields
        namespace_id_env = config.get("namespace_id_env") or "AGENTSET_NAMESPACE_ID"

        # Validate environment variables exist
        if not os.getenv(config["api_key_env"]):
            raise ConfigurationError(
                f"Environment variable {config['api_key_env']} is not set"
            )

        if not os.getenv(namespace_id_env):
            raise ConfigurationError(
                f"Environment variable {namespace_id_env} is not set"
            )

    def get_required_env_vars(self) -> list[str]:
        """Get list of required environment variables.

        Returns:
            List of required environment variable names
        """
        return [self.config.api_key_env, self.namespace_id_env]

    def get_options_schema(self) -> dict[str, Any]:
        """Get JSON schema for Agentset configuration options.

        Returns:
            JSON schema for configuration options
        """
        return {
            "type": "object",
            "properties": {
                "namespace_id_env": {
                    "type": "string",
                    "description": "Environment variable name for namespace ID",
                    "default": "AGENTSET_NAMESPACE_ID",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds",
                    "minimum": 1,
                    "default": 60,
                },
                "default_top_k": {
                    "type": "integer",
                    "description": "Default number of results",
                    "minimum": 1,
                    "default": 5,
                },
                "rerank": {
                    "type": "boolean",
                    "description": "Enable result reranking",
                    "default": True,
                },
            },
            "required": [],
        }


# Register adapter on import
from .registry import register_adapter

register_adapter(AgentsetAdapter)
