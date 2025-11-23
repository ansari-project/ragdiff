"""Goodmem provider for RAGDiff v2.0.

Next-generation RAG system using Goodmem for memory retrieval across multiple spaces.
Supports both HTTP API (streaming) and CLI-based search with automatic fallback.

Configuration:
    api_key: API key for Goodmem (string, required)
    base_url: API base URL (string, default: "http://ansari.hosted.pairsys.ai:8080")
    space_ids: List of space IDs to search (list[str], default: Ibn Katheer, Mawsuah, Qurtubi)
    timeout: Request timeout seconds (int, default: 30)

Example:
    >>> provider = GoodmemProvider(config={
    ...     "api_key": "your-key",
    ...     "space_ids": ["efd91f05-87cf-4c4c-a04d-0a970f8d30a7"],
    ...     "base_url": "http://ansari.hosted.pairsys.ai:8080"
    ... })
    ...
    >>> chunks = provider.search("What is tafsir?", top_k=5)
"""

import json
import os
import subprocess
from typing import Any

import requests

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import RetrievedChunk, SearchResult
from ..core.pricing import count_tokens
from .abc import Provider

logger = get_logger(__name__)

# Optional Goodmem client import
try:
    from goodmem_client import ApiClient, Configuration
    from goodmem_client.streaming import MemoryStreamClient

    GOODMEM_AVAILABLE = True
except ImportError:
    GOODMEM_AVAILABLE = False
    logger.warning("goodmem-client not installed. Using CLI fallback only.")
    ApiClient = None  # type: ignore
    Configuration = None  # type: ignore
    MemoryStreamClient = None  # type: ignore

# Space ID to human-readable name mapping
_SPACE_NAMES = {
    "d2352bfe-e6d3-43c8-8b8e-2ea280068743": "Ibn Katheer",
    "dd747fa8-7ae6-4550-992c-04d4447c4306": "Mawsuah",
    "308764dc-fb1e-4877-9b09-831fafefbd9a": "Qurtubi",
    "d21f4578-6a95-4478-ad04-48eddd2e6c64": "Sunnah",
    # Legacy IDs (kept for backward compatibility)
    "efd91f05-87cf-4c4c-a04d-0a970f8d30a7": "Ibn Katheer (Legacy)",
    "2d1f3227-8331-46ee-9dc2-d9265bfc79f5": "Mawsuah (Legacy)",
    "d04d8032-3a9b-4b83-b906-e48458715a7a": "Qurtubi (Legacy)",
}


class GoodmemProvider(Provider):
    """Goodmem memory retrieval provider.

    Searches across multiple Goodmem spaces using HTTP API or CLI.
    """

    def __init__(self, config: dict):
        """Initialize Goodmem provider.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigError: If required config missing or invalid
        """
        super().__init__(config)

        # Validate required fields
        if "api_key" not in config:
            raise ConfigError("Goodmem provider requires 'api_key' in config")

        self.api_key = config["api_key"]
        self.base_url = config.get("base_url", "http://ansari.hosted.pairsys.ai:8080")
        self.timeout = config.get("timeout", 30)
        self.reranker_id = config.get("reranker_id")

        # Default space IDs (Ibn Katheer, Mawsuah, Qurtubi)
        self.space_ids = config.get("space_ids") or [
            "d2352bfe-e6d3-43c8-8b8e-2ea280068743",
            "dd747fa8-7ae6-4550-992c-04d4447c4306",
            "308764dc-fb1e-4877-9b09-831fafefbd9a",
        ]

        # Initialize Goodmem client if available
        if GOODMEM_AVAILABLE:
            try:
                configuration = Configuration(host=self.base_url)
                configuration.api_key["ApiKeyAuth"] = self.api_key

                self.api_client = ApiClient(configuration)
                self.stream_client = MemoryStreamClient(self.api_client)

                # Ensure REST client is initialized
                if not hasattr(self.api_client, "rest_client"):
                    from goodmem_client.rest import RESTClientObject

                    self.api_client.rest_client = RESTClientObject(configuration)

                logger.info(
                    f"Goodmem client initialized with host: {self.base_url}, "
                    f"spaces: {self.space_ids}, reranker: {self.reranker_id}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Goodmem client: {e}")
                self.stream_client = None
        else:
            self.stream_client = None
            logger.warning(
                "Running in CLI-only mode - install goodmem-client for HTTP API"
            )

        logger.debug(
            f"Initialized Goodmem provider: {len(self.space_ids)} spaces, "
            f"api={GOODMEM_AVAILABLE}"
        )

    def search(self, query: str, top_k: int = 5) -> SearchResult:
        """Search Goodmem for relevant documents.

        Args:
            query: Search query text
            top_k: Maximum results to return

        Returns:
            SearchResult object

        Raises:
            RunError: If search fails
        """
        # Try HTTP API first if available
        if GOODMEM_AVAILABLE and self.stream_client:
            try:
                return self._search_via_api(query, top_k)
            except Exception as e:
                logger.warning(f"API search failed, falling back to CLI: {e}")

        # Fall back to CLI-based search
        return self._search_via_cli(query, top_k)

    def _search_via_api(self, query: str, top_k: int) -> SearchResult:
        """Search Goodmem using HTTP API.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            SearchResult object

        Raises:
            RunError: If API request fails
        """
        results: list[RetrievedChunk] = []
        total_tokens_returned = 0

        logger.info(f"Searching {len(self.space_ids)} Goodmem spaces via API")

        try:
            # Query all spaces in a single request
            requested_size = max(top_k, top_k * 10)
            params = {
                "message": query,
                "spaceIds": ",".join(self.space_ids),
                "requestedSize": str(requested_size),
                "pp_max_results": str(top_k),
                "pp_chronological_resort": "false",
            }

            if self.reranker_id:
                params["pp_reranker_id"] = self.reranker_id

            # Make HTTP request
            url = f"{self.api_client.configuration.host}/v1/memories:retrieve"
            headers = {"Accept": "application/x-ndjson", "x-api-key": self.api_key}

            response = requests.get(
                url, params=params, headers=headers, timeout=self.timeout
            )

            if response.status_code != 200:
                raise RunError(f"Goodmem API returned HTTP {response.status_code}")

            # Parse NDJSON response
            memory_to_space = {}
            rerank_result_set_ids = set()
            current_stage = None
            encountered_rerank = False

            for line in response.text.strip().split("\n"):
                if line:
                    try:
                        event = json.loads(line)

                        # Track stage boundaries
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

                        # Extract memoryId -> spaceId mapping
                        if event.get("memoryDefinition"):
                            mem_def = event["memoryDefinition"]
                            memory_id = mem_def.get("memoryId")
                            space_id = mem_def.get("spaceId")
                            if memory_id and space_id:
                                memory_to_space[memory_id] = space_id

                        # Parse retrieved items
                        if (
                            event
                            and "retrievedItem" in event
                            and event["retrievedItem"]
                        ):
                            item = event["retrievedItem"]
                            chunk_ref = item.get("chunk", {})
                            result_set_id = chunk_ref.get("resultSetId")

                            # Only include rerank results if reranking occurred
                            if self.reranker_id and rerank_result_set_ids:
                                if result_set_id not in rerank_result_set_ids:
                                    continue
                            elif (
                                current_stage
                                and current_stage != "rerank"
                                and self.reranker_id
                            ):
                                # If we expected reranking but haven't seen it yet (or failed),
                                # we might want to be careful. But let's just filter by stage if possible.
                                # For now, trusting the result_set_id check above.
                                pass

                            # Standard parsing logic...
                            if chunk_ref:
                                chunk = chunk_ref.get("chunk", {})
                                text = chunk.get("chunkText", "")
                                score = abs(chunk_ref.get("relevanceScore", 0.5))

                                # Get space_id from memory mapping
                                memory_id = chunk.get("memoryId")
                                space_id = memory_to_space.get(memory_id, "unknown")

                                if text:
                                    # Count tokens
                                    chunk_tokens = count_tokens("gpt-4o-mini", text)
                                    total_tokens_returned += chunk_tokens

                                    result = RetrievedChunk(
                                        content=text,
                                        score=self._normalize_score(score),
                                        token_count=chunk_tokens,
                                        metadata={
                                            "source": _SPACE_NAMES.get(
                                                space_id, "GoodMem"
                                            ),
                                            "space_id": space_id,
                                            "result_set_id": result_set_id,
                                            "stage": current_stage,
                                        },
                                    )
                                    results.append(result)
                    except json.JSONDecodeError:
                        continue

            if self.reranker_id and not encountered_rerank:
                logger.warning(
                    f"Goodmem stream did not include rerank stage for query: {query} despite reranker_id being set."
                )

        except Exception as e:
            raise RunError(f"Goodmem API search failed: {e}") from e

        # Sort by score and return top_k
        results.sort(key=lambda x: x.score or 0, reverse=True)
        top_results = results[:top_k]

        # Update total tokens to reflect only the returned chunks if we filtered
        # Actually, keeping total retrieved is interesting, but let's match others: total tokens in result
        total_tokens_returned = sum(c.token_count for c in top_results if c.token_count)

        return SearchResult(
            chunks=top_results,
            total_tokens_returned=total_tokens_returned,
            cost=None,
            metadata={},
        )

    def _search_via_cli(self, query: str, top_k: int) -> SearchResult:
        """Search Goodmem using CLI tool.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            SearchResult object

        Raises:
            RunError: If CLI search fails for all spaces
        """
        results = []
        total_tokens_returned = 0

        # Search each space using CLI
        for space_id in self.space_ids:
            try:
                cmd = [
                    "goodmem",
                    "memory",
                    "retrieve",
                    query,
                    "--space-id",
                    space_id,
                    "--server",
                    "https://ansari.hosted.pairsys.ai:9090",
                    "--max-results",
                    str(top_k),
                    "--format",
                    "json",
                ]

                if self.reranker_id:
                    args = json.dumps({"reranker_id": self.reranker_id})
                    cmd.extend(["--post-processor-args", args])

                # Set environment with API key
                env = os.environ.copy()
                env["GOODMEM_API_KEY"] = self.api_key

                # Execute command
                logger.info(f"Searching Goodmem space {space_id} via CLI")
                result = subprocess.run(
                    cmd, capture_output=True, text=True, env=env, timeout=self.timeout
                )

                if result.returncode != 0:
                    logger.warning(
                        f"CLI search failed for space {space_id}: {result.stderr}"
                    )
                    continue

                # Parse JSON output
                try:
                    data = json.loads(result.stdout)
                    parsed = self._parse_cli_response(data, space_id)
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

        if not results:
            raise RunError(
                f"Goodmem CLI search failed for all {len(self.space_ids)} spaces"
            )

        # Sort by score and return top_k
        results.sort(key=lambda x: x.score or 0, reverse=True)
        top_results = results[:top_k]

        total_tokens_returned = sum(c.token_count for c in top_results if c.token_count)

        return SearchResult(
            chunks=top_results,
            total_tokens_returned=total_tokens_returned,
            cost=None,
            metadata={},
        )

    def _parse_cli_response(
        self, data: dict[str, Any], space_id: str
    ) -> list[RetrievedChunk]:
        """Parse CLI JSON response into RetrievedChunk objects.

        Args:
            data: JSON response from CLI
            space_id: Space ID for source naming

        Returns:
            List of RetrievedChunk objects
        """
        chunks = []
        source = _SPACE_NAMES.get(space_id, "GoodMem")

        # Parse retrieved chunks
        retrieved = data.get("retrieved", [])
        for item in retrieved:
            try:
                # Extract chunk data
                result_data = item.get("Result", {})
                chunk_data = result_data.get("Chunk", {})
                chunk = chunk_data.get("chunk", {})

                # Get text and score
                text = chunk.get("chunk_text", "")
                score = abs(chunk_data.get("relevance_score", 0.5))

                if text:
                    # Count tokens
                    chunk_tokens = count_tokens("gpt-4o-mini", text)

                    result = RetrievedChunk(
                        content=text,
                        score=self._normalize_score(score),
                        token_count=chunk_tokens,
                        metadata={
                            "source": source,
                            "space_id": space_id,
                            "chunk_id": chunk.get("chunk_id", ""),
                            "memory_id": chunk.get("memory_id", ""),
                        },
                    )
                    chunks.append(result)

            except Exception as e:
                logger.debug(f"Failed to parse CLI result item: {e}")
                continue

        return chunks

    def _normalize_score(self, score: float) -> float:
        """Normalize Goodmem score to 0-1 range.

        Args:
            score: Raw score from Goodmem

        Returns:
            Normalized score in 0-1 range
        """
        # Goodmem scores are typically in range [0, 10+]
        # Normalize to 0-1 using sigmoid-like function
        return min(1.0, abs(score) / 10.0)


# Register the provider
from .registry import register_tool  # noqa: E402

register_tool("goodmem", GoodmemProvider)
