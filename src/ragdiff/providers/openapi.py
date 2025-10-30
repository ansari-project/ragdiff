"""OpenAPI provider for RAGDiff v2.0.

A generic provider that can query any REST API using OpenAPI-style configuration.
Uses JMESPath for flexible response mapping and supports multiple auth schemes.

Configuration:
    base_url: API base URL (string, required)
    endpoint: API endpoint path (string, required)
    method: HTTP method (string, optional, default: "POST")
    auth: Authentication config (dict, required)
    request_body: Request body template (dict, optional)
    request_params: Query parameters template (dict, optional)
    response_mapping: JMESPath mappings (dict, required)
    timeout: Request timeout seconds (int, optional, default: 30)
    retry_count: Number of retries (int, optional, default: 3)
    retry_delay: Delay between retries (int, optional, default: 1)

Example:
    >>> provider = OpenAPIProvider(config={
    ...     "base_url": "https://api.example.com",
    ...     "endpoint": "/v1/search",
    ...     "method": "POST",
    ...     "auth": {"type": "bearer", "header": "Authorization", "scheme": "Bearer"},
    ...     "api_key": "sk_...",
    ...     "request_body": {"query": "${query}", "limit": "${top_k}"},
    ...     "response_mapping": {
    ...         "results_array": "data.results",
    ...         "fields": {
    ...             "id": "id",
    ...             "text": "content",
    ...             "score": "score"
    ...         }
    ...     }
    ... })
    >>> chunks = provider.search("What is RAG?", top_k=5)
"""

import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models import RetrievedChunk
from .abc import Provider
from .openapi_utils import ResponseMapper, TemplateEngine

logger = get_logger(__name__)


class OpenAPIProvider(Provider):
    """Generic OpenAPI/REST API provider.

    Connects to any REST API using configuration-driven approach.
    No code needed - just YAML configuration.
    """

    def __init__(self, config: dict):
        """Initialize OpenAPI provider.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigError: If required config missing or invalid
        """
        super().__init__(config)

        # Validate required fields
        required = ["base_url", "endpoint", "auth", "response_mapping"]
        for field in required:
            if field not in config:
                raise ConfigError(f"OpenAPI provider requires '{field}' in config")

        self.base_url = config["base_url"].rstrip("/")
        self.endpoint = config["endpoint"]
        self.method = config.get("method", "POST").upper()
        self.auth_config = config["auth"]
        self.timeout = config.get("timeout", 30)
        self.retry_count = config.get("retry_count", 3)
        self.retry_delay = config.get("retry_delay", 1)

        # Request templates
        self.request_body_template = config.get("request_body")
        self.request_params_template = config.get("request_params")

        # Initialize response mapper and template engine
        self.response_mapper = ResponseMapper(config["response_mapping"])
        self.template_engine = TemplateEngine()

        # Extract API key if needed
        self.api_key = config.get("api_key")

        logger.debug(
            f"Initialized OpenAPI provider: {self.method} {self.base_url}{self.endpoint}"
        )

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search via REST API.

        Args:
            query: Search query text
            top_k: Maximum results to return

        Returns:
            List of RetrievedChunk objects

        Raises:
            RunError: If API request fails
        """
        # Build request with variable substitution
        variables = {"query": query, "top_k": top_k}

        # Build request body
        request_body = None
        if self.request_body_template:
            request_body = self.template_engine.render(
                self.request_body_template, variables
            )

        # Build query params
        request_params = None
        if self.request_params_template:
            request_params = self.template_engine.render(
                self.request_params_template, variables
            )

        # Execute request with retries
        url = f"{self.base_url}{self.endpoint}"
        response_json = self._execute_with_retry(
            url, request_body, request_params, self.retry_count
        )

        # Map response to chunks
        try:
            chunks = self.response_mapper.map_results(response_json)
            # Convert to RetrievedChunk if needed
            retrieved_chunks = []
            for chunk in chunks:
                if hasattr(chunk, "content"):
                    # Already a RetrievedChunk-like object
                    retrieved_chunks.append(
                        RetrievedChunk(
                            content=chunk.content,
                            score=chunk.score,
                            metadata=chunk.metadata or {},
                        )
                    )
                elif hasattr(chunk, "text"):
                    # RagResult object from legacy v1.x compatibility
                    retrieved_chunks.append(
                        RetrievedChunk(
                            content=chunk.text,
                            score=chunk.score,
                            metadata=chunk.metadata or {},
                        )
                    )
                else:
                    # It's a dict
                    retrieved_chunks.append(
                        RetrievedChunk(
                            content=chunk.get("content", ""),
                            score=chunk.get("score"),
                            metadata=chunk.get("metadata", {}),
                        )
                    )

            # Sort and limit
            if any(c.score is not None for c in retrieved_chunks):
                retrieved_chunks.sort(key=lambda x: x.score or 0, reverse=True)

            return retrieved_chunks[:top_k]

        except Exception as e:
            raise RunError(f"Failed to map API response: {e}") from e

    def _execute_with_retry(
        self,
        url: str,
        request_body: Any,
        request_params: Any,
        retries_left: int,
    ) -> dict:
        """Execute HTTP request with exponential backoff retry.

        Args:
            url: Request URL
            request_body: Request body (or None)
            request_params: Query parameters (or None)
            retries_left: Number of retries remaining

        Returns:
            Response JSON as dict

        Raises:
            RunError: If all retries exhausted
        """
        try:
            # Build auth
            headers = {}
            auth = None

            if self.auth_config.get("type") == "bearer":
                if not self.api_key:
                    raise ConfigError("Bearer auth requires api_key in config")
                scheme = self.auth_config.get("scheme", "Bearer")
                header_name = self.auth_config.get("header", "Authorization")
                headers[header_name] = f"{scheme} {self.api_key}"

            elif self.auth_config.get("type") == "apikey":
                if not self.api_key:
                    raise ConfigError("API Key auth requires api_key in config")
                location = self.auth_config.get("location", "header")
                param_name = self.auth_config.get("parameter_name", "api_key")

                if location == "header":
                    headers[param_name] = self.api_key
                elif location == "query":
                    if request_params is None:
                        request_params = {}
                    request_params[param_name] = self.api_key

            elif self.auth_config.get("type") == "basic":
                username = self.config.get("username")
                password = self.config.get("password")
                if not username or not password:
                    raise ConfigError(
                        "Basic auth requires username and password in config"
                    )
                auth = HTTPBasicAuth(username, password)

            # Execute request
            response = requests.request(
                method=self.method,
                url=url,
                json=request_body if request_body else None,
                params=request_params if request_params else None,
                headers=headers if headers else None,
                auth=auth,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if retries_left > 0:
                logger.warning(
                    f"API request failed, retrying... ({retries_left} retries left): {e}"
                )
                time.sleep(self.retry_delay * (self.retry_count - retries_left + 1))
                return self._execute_with_retry(
                    url, request_body, request_params, retries_left - 1
                )
            else:
                raise RunError(f"API request failed after all retries: {e}") from e


# Register the provider
from .registry import register_tool  # noqa: E402

register_tool("openapi", OpenAPIProvider)
