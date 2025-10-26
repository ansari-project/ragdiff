"""Generic OpenAPI adapter for RAGDiff.

This adapter can query any REST API by reading configuration from YAML.
It uses JMESPath for flexible response mapping and supports multiple
authentication schemes.
"""

import logging
import time
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from ..core.errors import AdapterError, ConfigurationError
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter
from .openapi_mapping import ResponseMapper, TemplateEngine

logger = logging.getLogger(__name__)


class OpenAPIAdapter(RagAdapter):
    """Generic adapter for OpenAPI/REST APIs.

    Reads configuration from YAML options dict:
    - base_url: API base URL
    - endpoint: API endpoint path
    - method: HTTP method (GET, POST, etc.)
    - auth: Authentication configuration
    - request_body: Template for request body
    - request_params: Template for query parameters
    - response_mapping: JMESPath mappings for response fields

    Example config:
        ```yaml
        my-api:
          adapter: openapi
          api_key_env: MY_API_KEY
          options:
            base_url: https://api.example.com
            endpoint: /v1/search
            method: POST
            auth:
              type: bearer
              header: Authorization
              scheme: Bearer
            request_body:
              query: "${query}"
              limit: ${top_k}
            response_mapping:
              results_array: "data.results"
              fields:
                id: "id"
                text: "content.text"
                score: "relevance_score"
                source: "source.name"
        ```
    """

    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "openapi"

    def __init__(self, config: ToolConfig, credentials: Optional[dict[str, str]] = None):
        """Initialize OpenAPI adapter.

        Args:
            config: Tool configuration
            credentials: Optional credentials dict (overrides env vars)

        Raises:
            ConfigurationError: If configuration is invalid
        """
        super().__init__(config, credentials)

        # Extract options dict
        if not config.options:
            raise ConfigurationError("OpenAPI adapter requires 'options' configuration")

        self.options = config.options
        self.timeout = config.timeout
        self.max_retries = config.max_retries

        # Validate and extract required config
        self.validate_config(self.options)

        # Extract configuration
        self.base_url = self.options["base_url"].rstrip("/")
        self.endpoint = self.options["endpoint"]
        self.method = self.options.get("method", "POST").upper()
        self.auth_config = self.options["auth"]

        # Get API credentials
        self.api_key = self._get_credential(config.api_key_env)
        if not self.api_key:
            raise ConfigurationError(
                f"API key not found in environment: {config.api_key_env}"
            )

        # For basic auth, might need additional credentials
        if self.auth_config["type"] == "basic":
            username_env = self.auth_config.get("username_env", config.api_key_env)
            password_env = self.auth_config.get("password_env", config.api_key_env)
            self.username = self._get_credential(username_env) or ""
            self.password = self._get_credential(password_env) or ""

        # Initialize mapping engine
        response_mapping = self.options["response_mapping"]
        self.response_mapper = ResponseMapper(response_mapping)

        # Initialize template engine
        self.template_engine = TemplateEngine()

        # Optional request templates
        self.request_body_template = self.options.get("request_body")
        self.request_params_template = self.options.get("request_params")
        self.request_headers_template = self.options.get("request_headers", {})

        logger.info(
            f"OpenAPI adapter initialized: {self.method} {self.base_url}{self.endpoint}"
        )

    def validate_config(self, config: dict[str, Any]) -> None:
        """Validate OpenAPI adapter configuration.

        Args:
            config: Configuration dict (options)

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Required fields
        required_fields = ["base_url", "endpoint", "auth", "response_mapping"]
        for field in required_fields:
            if field not in config:
                raise ConfigurationError(
                    f"OpenAPI adapter missing required field: {field}"
                )

        # Validate auth configuration
        auth = config["auth"]
        if not isinstance(auth, dict):
            raise ConfigurationError("auth must be a dict")
        if "type" not in auth:
            raise ConfigurationError("auth missing 'type' field")

        auth_type = auth["type"]
        valid_auth_types = ["bearer", "api_key", "basic"]
        if auth_type not in valid_auth_types:
            raise ConfigurationError(
                f"Invalid auth type '{auth_type}'. Must be one of: {valid_auth_types}"
            )

        # Type-specific validation
        if auth_type in ["bearer", "api_key"]:
            if "header" not in auth:
                raise ConfigurationError(f"auth type '{auth_type}' requires 'header'")

        # Validate response_mapping
        response_mapping = config["response_mapping"]
        if not isinstance(response_mapping, dict):
            raise ConfigurationError("response_mapping must be a dict")
        if "results_array" not in response_mapping:
            raise ConfigurationError("response_mapping missing 'results_array'")
        if "fields" not in response_mapping:
            raise ConfigurationError("response_mapping missing 'fields'")

        # Validate required fields in mapping
        required_mapping_fields = ["id", "text", "score"]
        fields = response_mapping["fields"]
        for field in required_mapping_fields:
            if field not in fields:
                raise ConfigurationError(
                    f"response_mapping.fields missing required field: {field}"
                )

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Execute search via OpenAPI endpoint.

        Args:
            query: Search query string
            top_k: Number of results to return

        Returns:
            List of RagResult objects

        Raises:
            AdapterError: If API call or mapping fails
        """
        start_time = time.time()

        try:
            # Build request
            request_dict = self._build_request(query, top_k)

            # Execute request with retries
            response_json = self._execute_request(request_dict)

            # Map response to RagResults
            rag_results = self.response_mapper.map_results(response_json)

            # Add latency to each result
            latency_ms = (time.time() - start_time) * 1000
            for result in rag_results:
                result.latency_ms = latency_ms

            # Sort by score descending and limit to top_k
            rag_results.sort(key=lambda x: x.score, reverse=True)
            rag_results = rag_results[:top_k]

            logger.info(
                f"OpenAPI search returned {len(rag_results)} results in {latency_ms:.2f}ms"
            )
            return rag_results

        except ConfigurationError:
            # Re-raise configuration errors as-is
            raise
        except Exception as e:
            raise AdapterError(f"OpenAPI search failed: {e}") from e

    def _build_request(self, query: str, top_k: int) -> dict[str, Any]:
        """Build HTTP request with template substitution.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Request dict with url, method, headers, json, params
        """
        # Template variables
        variables = {"query": query, "top_k": top_k}

        # Build URL
        url = f"{self.base_url}{self.endpoint}"

        # Build headers
        headers = self._build_headers()

        # Apply header template if provided
        if self.request_headers_template:
            custom_headers = self.template_engine.render(
                self.request_headers_template, variables
            )
            headers.update(custom_headers)

        # Build request body (JSON)
        json_body = None
        if self.request_body_template:
            json_body = self.template_engine.render(
                self.request_body_template, variables
            )

        # Build query parameters
        params = None
        if self.request_params_template:
            params = self.template_engine.render(
                self.request_params_template, variables
            )

        return {
            "url": url,
            "method": self.method,
            "headers": headers,
            "json": json_body,
            "params": params,
        }

    def _build_headers(self) -> dict[str, str]:
        """Build authentication headers.

        Returns:
            Dict of HTTP headers with authentication
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        auth_type = self.auth_config["type"]

        if auth_type == "bearer":
            # Bearer token: Authorization: Bearer {token}
            header_name = self.auth_config["header"]
            scheme = self.auth_config.get("scheme", "Bearer")
            headers[header_name] = f"{scheme} {self.api_key}"

        elif auth_type == "api_key":
            # API Key header: {header_name}: {key}
            header_name = self.auth_config["header"]
            headers[header_name] = self.api_key

        # Basic auth is handled separately in _execute_request

        return headers

    def _execute_request(self, request_dict: dict[str, Any]) -> dict:
        """Execute HTTP request with retry logic.

        Args:
            request_dict: Request configuration

        Returns:
            Parsed JSON response

        Raises:
            AdapterError: If request fails after retries
        """
        url = request_dict["url"]
        method = request_dict["method"]
        headers = request_dict["headers"]
        json_body = request_dict.get("json")
        params = request_dict.get("params")

        # Prepare auth for basic auth
        auth = None
        if self.auth_config["type"] == "basic":
            auth = HTTPBasicAuth(self.username, self.password)

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"OpenAPI request attempt {attempt + 1}/{self.max_retries}: "
                    f"{method} {url}"
                )

                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params,
                    auth=auth,
                    timeout=self.timeout,
                )

                # Raise for HTTP errors (4xx, 5xx)
                response.raise_for_status()

                # Parse JSON
                return response.json()

            except requests.exceptions.HTTPError as e:
                # HTTP errors (4xx, 5xx) - don't retry on client errors
                if e.response.status_code < 500:
                    raise AdapterError(
                        f"HTTP {e.response.status_code}: {e.response.text}"
                    ) from e
                last_exception = e

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Request timeout (attempt {attempt + 1})")

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error (attempt {attempt + 1})")

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Request error (attempt {attempt + 1}): {e}")

            # Exponential backoff before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                backoff = 2 ** attempt  # 1s, 2s, 4s, ...
                time.sleep(backoff)

        # All retries failed
        raise AdapterError(
            f"OpenAPI request failed after {self.max_retries} attempts: {last_exception}"
        ) from last_exception

    def get_required_env_vars(self) -> list[str]:
        """Return list of required environment variable names.

        Returns:
            List of env var names
        """
        env_vars = [self.config.api_key_env]

        # Add additional env vars for basic auth
        if self.auth_config["type"] == "basic":
            username_env = self.auth_config.get("username_env")
            password_env = self.auth_config.get("password_env")
            if username_env:
                env_vars.append(username_env)
            if password_env:
                env_vars.append(password_env)

        return env_vars

    def get_options_schema(self) -> dict[str, Any]:
        """Return JSON schema for OpenAPI adapter options.

        Returns:
            JSON schema dict
        """
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "API base URL (e.g., https://api.example.com)",
                },
                "endpoint": {
                    "type": "string",
                    "description": "API endpoint path (e.g., /v1/search)",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH"],
                    "default": "POST",
                    "description": "HTTP method",
                },
                "auth": {
                    "type": "object",
                    "description": "Authentication configuration",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["bearer", "api_key", "basic"],
                            "description": "Authentication type",
                        },
                        "header": {
                            "type": "string",
                            "description": "Header name for bearer/api_key auth",
                        },
                        "scheme": {
                            "type": "string",
                            "description": "Scheme for bearer auth (default: Bearer)",
                        },
                    },
                    "required": ["type"],
                },
                "request_body": {
                    "type": "object",
                    "description": "Request body template (supports ${query}, ${top_k})",
                },
                "request_params": {
                    "type": "object",
                    "description": "Query parameters template",
                },
                "request_headers": {
                    "type": "object",
                    "description": "Additional headers template",
                },
                "response_mapping": {
                    "type": "object",
                    "description": "JMESPath response mappings",
                    "properties": {
                        "results_array": {
                            "type": "string",
                            "description": "JMESPath to results array",
                        },
                        "fields": {
                            "type": "object",
                            "description": "Field mappings (id, text, score, source, metadata)",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "score": {"type": "string"},
                                "source": {"type": "string"},
                                "metadata": {"type": "string"},
                            },
                            "required": ["id", "text", "score"],
                        },
                    },
                    "required": ["results_array", "fields"],
                },
            },
            "required": ["base_url", "endpoint", "auth", "response_mapping"],
        }


# Register adapter
from .registry import register_adapter

register_adapter(OpenAPIAdapter)
