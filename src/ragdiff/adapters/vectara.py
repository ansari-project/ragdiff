"""Vectara adapter for RAG search.

This adapter connects to the Vectara platform and can be used with different
corpora (e.g., Tafsir, Mawsuah) by configuring the corpus_id.
"""

import logging
import os
from typing import Any

import requests

from ..core.errors import AdapterError, ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

logger = logging.getLogger(__name__)


class VectaraAdapter(RagAdapter):
    """Adapter for Vectara RAG platform.

    Can be configured for different corpora (Tafsir, Mawsuah) via corpus_id.
    """

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "vectara"

    def __init__(self, config: ToolConfig, credentials: dict[str, str] | None = None):
        """Initialize Vectara adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides
        """
        super().__init__(config, credentials)
        self.validate_config(config.__dict__)

        # Get credentials from override or environment
        api_key = self._get_credential(config.api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"Missing API key environment variable: {config.api_key_env}"
            )

        # Store configuration
        self.api_key = api_key
        self.corpus_id = config.corpus_id
        self.base_url = config.base_url or "https://api.vectara.io"
        self.timeout = config.timeout or 60
        self.default_top_k = config.default_top_k or 5
        self.name = config.name
        self.description = "Vectara RAG platform"

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search Vectara for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        try:
            # Prepare Vectara v2 API request
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": self.api_key,
            }

            # Vectara v2 API format
            request_body = {
                "query": query,
                "search": {"corpora": [{"corpus_key": self.corpus_id}], "limit": top_k},
            }

            # Make API request
            response = requests.post(
                f"{self.base_url}/v2/query",
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()

            # Parse Vectara v2 response
            results = []
            for i, doc in enumerate(data.get("search_results", [])[:top_k]):
                # Extract text and metadata
                text = doc.get("text", "")
                score = doc.get("score", 0.0)

                # Combine part and document metadata
                metadata = {}
                if doc.get("part_metadata"):
                    metadata.update(doc["part_metadata"])
                if doc.get("document_metadata"):
                    metadata.update(doc["document_metadata"])

                # Determine source from metadata
                source = metadata.get("tafsir", "Tafsir")
                if metadata.get("surah"):
                    source = f"{source} - Surah {metadata['surah']}"

                # Create normalized result
                result = RagResult(
                    id=doc.get("document_id", f"doc_{i}"),
                    text=text,
                    score=self._normalize_score(score),
                    source=source,
                    metadata=metadata,
                )
                results.append(result)

            # Check for summary in v2 response
            if data.get("summary"):
                summary_text = data.get("summary", {}).get("text", "")
                if summary_text:
                    summary_result = RagResult(
                        id="summary",
                        text=summary_text,
                        score=1.0,
                        source="Summary",
                        metadata={"type": "summary"},
                    )
                    results.insert(0, summary_result)

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Vectara API request failed: {str(e)}")
            raise AdapterError(f"Vectara API request failed: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error in Vectara search: {str(e)}")
            raise AdapterError(f"Unexpected error in Vectara search: {str(e)}") from e

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate Vectara configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check required fields
        if not config.get("api_key_env"):
            raise ConfigurationError(
                "Vectara config missing required field: api_key_env"
            )

        if not config.get("corpus_id"):
            raise ConfigurationError("Vectara config missing required field: corpus_id")

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
        """Get JSON schema for Vectara configuration options.

        Returns:
            JSON schema for configuration options
        """
        return {
            "type": "object",
            "properties": {
                "corpus_id": {
                    "type": "string",
                    "description": "Vectara corpus ID",
                },
                "base_url": {
                    "type": "string",
                    "description": "Vectara API base URL",
                    "default": "https://api.vectara.io",
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
            },
            "required": ["corpus_id"],
        }

    def _normalize_score(self, score: float) -> float:
        """Normalize score to 0-1 range.

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

    def format_as_ref_list(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Format results as reference list for Claude.

        Args:
            results: Raw API response

        Returns:
            List of reference documents
        """
        ref_list = []

        if results.get("success") and results.get("results"):
            for result in results["results"]:
                if isinstance(result, RagResult):
                    ref = {
                        "text": result.text,
                        "source": result.source or "Vectara",
                        "score": result.score,
                        "metadata": result.metadata or {},
                    }
                    ref_list.append(ref)

        return ref_list


# Register adapter on import
from .registry import register_adapter

register_adapter(VectaraAdapter)
