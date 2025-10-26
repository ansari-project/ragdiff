"""Configuration generator for OpenAPI adapters.

Orchestrates the process of generating adapter configurations from OpenAPI specs.
"""

import json
import logging
from typing import Any, Optional

import requests

from ..adapters.openapi import OpenAPIAdapter
from ..core.errors import AdapterError, ConfigurationError
from ..core.models import ToolConfig
from .ai_analyzer import AIAnalyzer
from .parser import OpenAPISpec

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Generates adapter configurations from OpenAPI specifications.

    Orchestrates the complete workflow:
    1. Fetch and parse OpenAPI spec
    2. Identify search endpoint (AI or manual)
    3. Make test query to API
    4. Generate response mappings with AI
    5. Construct complete config
    6. Validate config
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize config generator.

        Args:
            model: LiteLLM model identifier for AI analysis
        """
        self.ai_analyzer = AIAnalyzer(model=model)
        logger.info(f"Config generator initialized with model: {model}")

    def generate(
        self,
        openapi_url: str,
        api_key: str,
        test_query: str,
        adapter_name: str,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Generate complete adapter configuration.

        Args:
            openapi_url: URL to OpenAPI specification
            api_key: API key for authentication
            test_query: Test query to execute
            adapter_name: Name for the adapter
            endpoint: Optional endpoint override (else AI identifies)
            method: Optional HTTP method override (else AI identifies)
            timeout: Request timeout in seconds

        Returns:
            Complete adapter configuration dict ready for YAML

        Raises:
            ConfigurationError: If generation fails at any step
            AdapterError: If test query fails
        """
        logger.info(f"Starting config generation for adapter '{adapter_name}'")

        # Step 1: Fetch and parse OpenAPI spec
        logger.info(f"Fetching OpenAPI spec from {openapi_url}")
        try:
            spec = OpenAPISpec.from_url(openapi_url, timeout=timeout)
        except Exception as e:
            raise ConfigurationError(f"Failed to fetch OpenAPI spec: {e}") from e

        # Get API info
        api_info = spec.get_info()
        base_url = api_info.get_base_url()

        if not base_url:
            raise ConfigurationError(
                "No server URL found in OpenAPI spec. Cannot determine base_url."
            )

        logger.info(f"API: {api_info.title} v{api_info.version}")
        logger.info(f"Base URL: {base_url}")

        # Step 2: Identify search endpoint
        if endpoint and method:
            logger.info(f"Using provided endpoint: {method} {endpoint}")
            search_endpoint_path = endpoint
            search_method = method.upper()
        else:
            logger.info("Using AI to identify search endpoint")
            endpoints = spec.get_endpoints()
            (
                search_endpoint_path,
                search_method,
                reasoning,
            ) = self.ai_analyzer.identify_search_endpoint(endpoints)
            logger.info(f"AI identified endpoint: {search_method} {search_endpoint_path}")
            logger.info(f"AI reasoning: {reasoning}")

        # Get endpoint details
        endpoint_info = spec.get_endpoint(search_endpoint_path, search_method)
        if not endpoint_info:
            raise ConfigurationError(
                f"Endpoint {search_method} {search_endpoint_path} not found in spec"
            )

        # Step 3: Determine authentication configuration
        auth_config = self._determine_auth_config(spec)

        # Step 4: Build test request and execute
        logger.info(f"Making test query: '{test_query}'")
        test_response = self._make_test_query(
            base_url=base_url,
            endpoint=search_endpoint_path,
            method=search_method,
            api_key=api_key,
            query=test_query,
            auth_config=auth_config,
            timeout=timeout,
        )

        logger.info("Test query successful, analyzing response")

        # Step 5: Generate response mapping with AI
        response_mapping = self.ai_analyzer.generate_response_mapping(test_response)

        # Step 6: Construct complete config
        config = self._build_config(
            adapter_name=adapter_name,
            base_url=base_url,
            endpoint=search_endpoint_path,
            method=search_method,
            auth_config=auth_config,
            response_mapping=response_mapping,
        )

        # Step 7: Validate config by creating adapter and testing
        logger.info("Validating generated config")
        self._validate_config(config, api_key, test_query)

        logger.info(f"Successfully generated config for '{adapter_name}'")
        return config

    def _determine_auth_config(self, spec: OpenAPISpec) -> dict[str, Any]:
        """Determine authentication configuration from spec.

        Args:
            spec: Parsed OpenAPI specification

        Returns:
            Auth configuration dict

        Raises:
            ConfigurationError: If no supported auth scheme found
        """
        auth_schemes = spec.get_auth_schemes()

        if not auth_schemes:
            logger.warning("No auth schemes found in spec, defaulting to bearer")
            return {
                "type": "bearer",
                "header": "Authorization",
                "scheme": "Bearer",
            }

        # Prefer bearer auth
        for auth in auth_schemes:
            if auth.type == "http" and auth.scheme == "bearer":
                logger.info(f"Using bearer auth scheme: {auth.name}")
                return {
                    "type": "bearer",
                    "header": "Authorization",
                    "scheme": "Bearer",
                }

        # Fallback to API key
        for auth in auth_schemes:
            if auth.type == "apiKey":
                logger.info(f"Using API key auth scheme: {auth.name}")
                return {
                    "type": "api_key",
                    "header": auth.parameter_name or "X-API-Key",
                }

        # If no supported scheme, default to bearer
        logger.warning("No supported auth scheme found, defaulting to bearer")
        return {
            "type": "bearer",
            "header": "Authorization",
            "scheme": "Bearer",
        }

    def _make_test_query(
        self,
        base_url: str,
        endpoint: str,
        method: str,
        api_key: str,
        query: str,
        auth_config: dict,
        timeout: int,
    ) -> dict:
        """Make a test query to the API.

        Args:
            base_url: API base URL
            endpoint: Endpoint path
            method: HTTP method
            api_key: API key for authentication
            query: Test query string
            auth_config: Auth configuration
            timeout: Request timeout

        Returns:
            Parsed JSON response

        Raises:
            AdapterError: If request fails
        """
        url = f"{base_url}{endpoint}"

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add authentication
        if auth_config["type"] == "bearer":
            scheme = auth_config.get("scheme", "Bearer")
            headers[auth_config["header"]] = f"{scheme} {api_key}"
        elif auth_config["type"] == "api_key":
            headers[auth_config["header"]] = api_key

        # Build request body (assume query and limit parameters)
        # This is a simplification - real implementation might need more sophistication
        request_body = {"query": query, "limit": 5}

        try:
            if method == "POST":
                response = requests.post(
                    url, json=request_body, headers=headers, timeout=timeout
                )
            elif method == "GET":
                response = requests.get(
                    url, params={"query": query, "limit": 5}, headers=headers, timeout=timeout
                )
            else:
                raise AdapterError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise AdapterError(f"Test query failed: {e}") from e

    def _build_config(
        self,
        adapter_name: str,
        base_url: str,
        endpoint: str,
        method: str,
        auth_config: dict,
        response_mapping: dict,
    ) -> dict[str, Any]:
        """Build complete adapter configuration.

        Args:
            adapter_name: Name for the adapter
            base_url: API base URL
            endpoint: Endpoint path
            method: HTTP method
            auth_config: Auth configuration
            response_mapping: Response mapping configuration

        Returns:
            Complete config dict
        """
        return {
            adapter_name: {
                "adapter": "openapi",
                "api_key_env": f"{adapter_name.upper()}_API_KEY",
                "timeout": 30,
                "max_retries": 3,
                "options": {
                    "base_url": base_url,
                    "endpoint": endpoint,
                    "method": method,
                    "auth": auth_config,
                    "request_body": {
                        "query": "${query}",
                        "limit": "${top_k}",
                    },
                    "response_mapping": response_mapping,
                },
            }
        }

    def _validate_config(
        self, config: dict, api_key: str, test_query: str
    ) -> None:
        """Validate configuration by creating adapter and testing.

        Args:
            config: Generated configuration
            api_key: API key for testing
            test_query: Test query string

        Raises:
            ConfigurationError: If config is invalid
            AdapterError: If test query fails
        """
        # Extract adapter name and config
        adapter_name = list(config.keys())[0]
        adapter_config = config[adapter_name]

        # Create ToolConfig
        tool_config = ToolConfig(
            name=adapter_name,
            api_key_env=adapter_config["api_key_env"],
            options=adapter_config["options"],
            timeout=adapter_config.get("timeout", 30),
            max_retries=adapter_config.get("max_retries", 3),
        )

        # Create adapter with test credentials
        credentials = {adapter_config["api_key_env"]: api_key}

        try:
            adapter = OpenAPIAdapter(tool_config, credentials=credentials)
        except Exception as e:
            raise ConfigurationError(f"Invalid configuration: {e}") from e

        # Execute test query
        try:
            results = adapter.search(test_query, top_k=5)
            logger.info(f"Validation successful: got {len(results)} results")

            if not results:
                logger.warning("Test query returned no results")

        except Exception as e:
            raise AdapterError(f"Test query failed: {e}") from e
