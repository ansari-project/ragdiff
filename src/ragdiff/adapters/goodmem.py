"""Goodmem adapter for RAG search."""

import json
import logging
import os
import subprocess
from typing import Any, Optional

import requests
import urllib3

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from ..core.errors import ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

logger = logging.getLogger(__name__)

# Import will be conditional based on availability
try:
    from goodmem_client import ApiClient, ApiException, Configuration
    from goodmem_client.streaming import MemoryStreamClient

    GOODMEM_AVAILABLE = True
    ApiClient_type = ApiClient
    Configuration_type = Configuration
    MemoryStreamClient_type = MemoryStreamClient
    ApiException_type = ApiException
except ImportError:
    GOODMEM_AVAILABLE = False
    ApiClient_type = None  # type: ignore[assignment,misc]
    Configuration_type = None  # type: ignore[assignment,misc]
    MemoryStreamClient_type = None  # type: ignore[assignment,misc]
    ApiException_type = None  # type: ignore[assignment,misc]
    logger.warning("goodmem-client not installed. Using mock implementation.")

# Space ID to human-readable name mapping
# This is a module-level constant (thread-safe, immutable)
_SPACE_NAMES = {
    "efd91f05-87cf-4c4c-a04d-0a970f8d30a7": "Ibn Katheer",
    "2d1f3227-8331-46ee-9dc2-d9265bfc79f5": "Mawsuah",
    "d04d8032-3a9b-4b83-b906-e48458715a7a": "Qurtubi",
}


class GoodmemAdapter(RagAdapter):
    """Adapter for Goodmem search tool."""

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "goodmem"

    def __init__(self, config: ToolConfig):
        """Initialize Goodmem adapter.

        Args:
            config: Tool configuration
        """
        self.config = config
        self.validate_config(config.__dict__)

        # Get credentials from environment
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"Missing API key environment variable: {config.api_key_env}"
            )

        # Store configuration
        self.api_key = api_key
        self.base_url = config.base_url or "http://ansari.hosted.pairsys.ai:8080"
        self.timeout = config.timeout or 60
        self.default_top_k = config.default_top_k or 5
        self.name = config.name
        self.description = "Next-generation RAG system using Goodmem"

        # Initialize Goodmem client if available
        if GOODMEM_AVAILABLE:
            try:
                # Configure API client - use port 8080 for HTTP REST API
                configuration = Configuration(
                    host=self.base_url or "http://ansari.hosted.pairsys.ai:8080",
                )
                configuration.api_key["ApiKeyAuth"] = self.api_key

                # Create API client and streaming client
                self.api_client = ApiClient(configuration)
                self.stream_client = MemoryStreamClient(self.api_client)

                # Ensure the REST client is initialized with proper SSL settings
                if not hasattr(self.api_client, "rest_client"):
                    from goodmem_client.rest import RESTClientObject

                    self.api_client.rest_client = RESTClientObject(configuration)

                # Get space IDs from config, with fallback to defaults
                self.space_ids = getattr(config, "space_ids", None) or [
                    "efd91f05-87cf-4c4c-a04d-0a970f8d30a7",  # Ibn Katheer
                    "2d1f3227-8331-46ee-9dc2-d9265bfc79f5",  # Mawsuah
                    "d04d8032-3a9b-4b83-b906-e48458715a7a",  # Qurtubi
                ]
                logger.info(
                    f"GoodMem client initialized with host: {configuration.host}, spaces: {self.space_ids}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize GoodMem client: {e}")
                self.stream_client = None  # type: ignore[assignment]
                self.space_ids = []
        else:
            self.stream_client = None  # type: ignore[assignment]
            # Still use configured space_ids even in mock mode
            self.space_ids = getattr(config, "space_ids", None) or [
                "efd91f05-87cf-4c4c-a04d-0a970f8d30a7",  # Ibn Katheer
                "2d1f3227-8331-46ee-9dc2-d9265bfc79f5",  # Mawsuah
                "d04d8032-3a9b-4b83-b906-e48458715a7a",  # Qurtubi
            ]
            logger.warning(
                "Running in mock mode - install goodmem-client for real functionality"
            )

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Search Goodmem for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        # Try the patched streaming client first
        if GOODMEM_AVAILABLE and self.stream_client:
            try:
                return self._search_via_streaming(query, top_k)
            except Exception as e:
                logger.warning(f"Streaming search failed, falling back to CLI: {e}")

        # Fall back to CLI-based implementation
        return self._search_via_cli(query, top_k)

    def _search_via_streaming(self, query: str, top_k: int) -> list[RagResult]:
        """Search GoodMem using HTTP API.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of RagResult objects
        """
        results: list[RagResult] = []

        logger.info(f"Searching {len(self.space_ids)} Goodmem spaces: {self.space_ids}")

        # Query all spaces in a single request
        try:
            # Build query parameters - pass all space IDs comma-separated
            # Retrieve significantly more candidates than we display so the reranker can
            # re-order a richer pool, then cap the emitted results to `top_k` without
            # resorting chronologically (we trust the reranker scores).
            requested_size = max(top_k, top_k * 10)
            params = {
                "message": query,
                "spaceIds": ",".join(self.space_ids),
                "requestedSize": str(requested_size),
                "pp_max_results": str(top_k),
                "pp_chronological_resort": "false",
            }

            logger.info(f"Querying all spaces in single request: {params['spaceIds']}")

            # Use requests directly for better streaming support
            url = f"{self.api_client.configuration.host}/v1/memories:retrieve"
            headers = {"Accept": "application/x-ndjson", "x-api-key": self.api_key}

            # Make HTTP request
            response = requests.get(url, params=params, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Failed to search spaces: HTTP {response.status_code}")
                return results

            # Parse NDJSON response and build mapping from memoryId to spaceId
            memory_to_space = {}
            rerank_result_set_ids = set()
            current_stage = None
            encountered_rerank = False

            for line in response.text.strip().split("\n"):
                if line:
                    try:
                        event = json.loads(line)
                        boundary = event.get("resultSetBoundary")
                        if boundary:
                            stage = boundary.get("stageName")
                            kind = boundary.get("kind")
                            result_set_id = boundary.get("resultSetId")
                            if stage:
                                current_stage = stage
                            if stage == "rerank" and result_set_id:
                                if kind == "BEGIN":
                                    rerank_result_set_ids.add(result_set_id)
                                    encountered_rerank = True

                        # Extract memoryId -> spaceId mapping from memoryDefinition events
                        if event.get("memoryDefinition"):
                            mem_def = event["memoryDefinition"]
                            memory_id = mem_def.get("memoryId")
                            space_id = mem_def.get("spaceId")
                            if memory_id and space_id:
                                memory_to_space[memory_id] = space_id

                        # Parse events similar to CLI response
                        if (
                            event
                            and "retrievedItem" in event
                            and event["retrievedItem"]
                        ):
                            item = event["retrievedItem"]
                            chunk_ref = item.get("chunk", {})
                            result_set_id = chunk_ref.get("resultSetId")

                            if rerank_result_set_ids:
                                if result_set_id not in rerank_result_set_ids:
                                    continue
                            elif current_stage and current_stage != "rerank":
                                continue
                            if chunk_ref:
                                chunk = chunk_ref.get("chunk", {})
                                text = chunk.get("chunkText", "")
                                score = abs(chunk_ref.get("relevanceScore", 0.5))

                                # Get space_id by looking up memoryId in our mapping
                                memory_id = chunk.get("memoryId")
                                space_id = memory_to_space.get(memory_id, "unknown")

                                if text:
                                    result = RagResult(
                                        id=f"goodmem_{len(results)}",
                                        text=text,
                                        score=self._normalize_score(score),
                                        source=_SPACE_NAMES.get(space_id, "GoodMem"),
                                        metadata={
                                            "space_id": space_id,
                                            "result_set_id": result_set_id,
                                            "stage": current_stage,
                                        },
                                    )
                                    results.append(result)
                    except json.JSONDecodeError:
                        continue

            if not encountered_rerank:
                logger.warning(
                    "GoodMem stream did not include a rerank stage; returning 0 results from query '%s'",
                    query,
                )

        except Exception as e:
            logger.warning(f"Failed to search spaces: {e}")

        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _search_via_cli(self, query: str, top_k: int) -> list[RagResult]:
        """Search GoodMem using the CLI tool.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of RagResult objects
        """
        results = []

        # Search each space using CLI
        for space_id in self.space_ids:
            try:
                # Build CLI command - CLI still uses gRPC port 9090
                cmd = [
                    "goodmem",
                    "memory",
                    "retrieve",
                    query,
                    "--space-id",
                    space_id,
                    "--server",
                    "https://ansari.hosted.pairsys.ai:9090",  # CLI uses gRPC
                    "--max-results",
                    str(top_k),
                    "--format",
                    "json",
                ]

                # Set environment with API key
                env = os.environ.copy()
                env["GOODMEM_API_KEY"] = self.api_key

                # Execute command
                logger.info(f"Searching GoodMem space {space_id} via CLI")
                result = subprocess.run(
                    cmd, capture_output=True, text=True, env=env, timeout=30
                )

                if result.returncode != 0:
                    logger.warning(
                        f"CLI search failed for space {space_id}: {result.stderr}"
                    )
                    continue

                # Parse JSON output
                try:
                    data = json.loads(result.stdout)
                    parsed = self._parse_cli_response(data, space_id, query)
                    results.extend(parsed)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse CLI JSON for space {space_id}: {e}"
                    )
                    continue

            except subprocess.TimeoutExpired:
                logger.warning(f"CLI search timed out for space {space_id}")
                continue
            except Exception as e:
                logger.warning(f"CLI search error for space {space_id}: {e}")
                continue

        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _parse_cli_response(
        self, data: dict[str, Any], space_id: str, query: str
    ) -> list[RagResult]:
        """Parse CLI JSON response into RagResult objects.

        Args:
            data: JSON response from CLI
            space_id: Space ID for source naming
            query: Original query

        Returns:
            List of RagResult objects
        """
        results = []

        # Map space ID to source name using module constant
        source = _SPACE_NAMES.get(space_id, "GoodMem")

        # Parse retrieved chunks
        retrieved = data.get("retrieved", [])
        for idx, item in enumerate(retrieved):
            try:
                # Extract chunk data
                result_data = item.get("Result", {})
                chunk_data = result_data.get("Chunk", {})
                chunk = chunk_data.get("chunk", {})

                # Get text and score
                text = chunk.get("chunk_text", "")
                # GoodMem uses negative scores, normalize them
                score = abs(chunk_data.get("relevance_score", 0.5))

                if text:
                    result = RagResult(
                        id=f"goodmem_{space_id[:8]}_{idx}",
                        text=text,
                        score=self._normalize_score(score),
                        source=source,
                        metadata={
                            "space_id": space_id,
                            "chunk_id": chunk.get("chunk_id", ""),
                            "memory_id": chunk.get("memory_id", ""),
                        },
                    )
                    results.append(result)

            except Exception as e:
                logger.debug(f"Failed to parse CLI result item {idx}: {e}")
                continue

        return results

    def _parse_stream_item(
        self, item: Any, space_id: str, index: int
    ) -> Optional[RagResult]:
        """Parse a single streaming item into a RagResult.

        Args:
            item: Retrieved item from the streaming response
            space_id: Space ID this item came from
            index: Index for ID generation

        Returns:
            RagResult or None if parsing fails
        """
        try:
            # Extract text content
            if hasattr(item, "content"):
                text = str(item.content)
            elif hasattr(item, "text"):
                text = str(item.text)
            elif hasattr(item, "chunk"):
                text = str(item.chunk)
            else:
                text = str(item)

            # Extract score if available
            score = float(getattr(item, "score", 0.5))

            # Map space ID to source name using module constant
            source = _SPACE_NAMES.get(space_id, "GoodMem")

            # Extract metadata if available
            metadata = {}
            if hasattr(item, "metadata") and item.metadata:
                metadata = item.metadata if isinstance(item.metadata, dict) else {}
            metadata["space_id"] = space_id

            return RagResult(
                id=f"goodmem_{space_id[:8]}_{index}",
                text=text,
                score=self._normalize_score(score),
                source=source,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to parse stream item: {e}")
            return None

    def _parse_goodmem_response(self, response: Any, query: str) -> list[RagResult]:
        """Parse Goodmem API response into normalized results.

        Args:
            response: Raw API response from Goodmem
            query: Original query

        Returns:
            List of normalized RagResult objects
        """
        results: list[RagResult] = []

        try:
            # The batch response should contain results for our single query
            if hasattr(response, "results"):
                # Response might be a list of results per query
                if isinstance(response.results, list) and len(response.results) > 0:
                    query_results = response.results[0]  # First query's results
                else:
                    query_results = response.results
            elif hasattr(response, "memories"):
                query_results = response.memories
            elif hasattr(response, "items"):
                query_results = response.items
            else:
                logger.warning(f"Unknown GoodMem response structure: {type(response)}")
                return results

            # Parse each memory item
            for idx, item in enumerate(query_results):
                try:
                    # Extract text content
                    if hasattr(item, "content"):
                        text = str(item.content)
                    elif hasattr(item, "text"):
                        text = str(item.text)
                    elif hasattr(item, "chunk"):
                        text = str(item.chunk)
                    else:
                        text = str(item)

                    # Extract score
                    score = float(getattr(item, "score", 0.5))

                    # Extract metadata and source
                    if hasattr(item, "metadata") and item.metadata:
                        metadata = (
                            item.metadata if isinstance(item.metadata, dict) else {}
                        )
                        source = metadata.get(
                            "space_name", metadata.get("source", "GoodMem Space")
                        )
                    else:
                        metadata = {}
                        source = "GoodMem"

                    # Add space information if available
                    if hasattr(item, "space_id"):
                        source = _SPACE_NAMES.get(item.space_id, source)
                        metadata["space_id"] = item.space_id

                    result = RagResult(
                        id=f"goodmem_{idx}",
                        text=text,
                        score=self._normalize_score(score),
                        source=source,
                        metadata=metadata,
                    )
                    results.append(result)

                except Exception as e:
                    logger.warning(f"Failed to parse GoodMem result item {idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing GoodMem response: {e}")

        return results

    def _mock_search(self, query: str, top_k: int) -> list[RagResult]:
        """Mock search for testing without Goodmem client.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Mock results for testing
        """
        mock_results = []
        for i in range(min(top_k, 3)):
            mock_results.append(
                RagResult(
                    id=f"goodmem_mock_{i}",
                    text=f"Mock Goodmem result {i+1} for query: {query}. "
                    f"This is a placeholder result for testing purposes. "
                    f"Install goodmem-client to get real results.",
                    score=0.9 - (i * 0.15),
                    source=f"Goodmem Mock Source {i+1}",
                    metadata={"mock": True, "index": i, "query": query},
                )
            )
        return mock_results

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate Goodmem configuration.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Check required fields
        if not config.get("api_key_env"):
            raise ConfigurationError(
                "Goodmem config missing required field: api_key_env"
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
        """Get JSON schema for Goodmem configuration options.

        Returns:
            JSON schema for configuration options
        """
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "Goodmem API base URL",
                    "default": "http://ansari.hosted.pairsys.ai:8080",
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
                "space_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Goodmem space IDs to search",
                },
            },
            "required": [],
        }


# Register adapter on import
from .registry import register_adapter

register_adapter(GoodmemAdapter)
