"""Configuration generator for OpenAPI providers.

Orchestrates the process of generating provider configurations from OpenAPI specs.
"""

import logging
from typing import Any, Optional

import requests

from ..core.errors import ConfigError, RunError
from ..providers.openapi import OpenAPIProvider
from .ai_analyzer import AIAnalyzer
from .parser import OpenAPISpec

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Generates provider configurations from OpenAPI specifications.

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
        provider_name: str,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Generate complete provider configuration.

        Args:
            openapi_url: URL to OpenAPI specification
            api_key: API key for authentication
            test_query: Test query to execute
            provider_name: Name for the provider
            endpoint: Optional endpoint override (else AI identifies)
            method: Optional HTTP method override (else AI identifies)
            timeout: Request timeout in seconds

        Returns:
            Complete provider configuration dict ready for YAML

        Raises:
            ConfigError: If generation fails at any step
            RunError: If test query fails
        """
        logger.info(f"Starting config generation for provider '{provider_name}'")

        # Step 1: Fetch and parse OpenAPI spec
        logger.info(f"Fetching OpenAPI spec from {openapi_url}")
        try:
            spec = OpenAPISpec.from_url(openapi_url, timeout=timeout)
        except Exception as e:
            raise ConfigError(f"Failed to fetch OpenAPI spec: {e}") from e

        # Get API info
        api_info = spec.get_info()
        base_url = api_info.get_base_url()

        if not base_url:
            raise ConfigError(
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
            logger.info(
                f"AI identified endpoint: {search_method} {search_endpoint_path}"
            )
            logger.info(f"AI reasoning: {reasoning}")

        # Get endpoint details
        endpoint_info = spec.get_endpoint(search_endpoint_path, search_method)
        if not endpoint_info:
            raise ConfigError(
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
            provider_name=provider_name,
            base_url=base_url,
            endpoint=search_endpoint_path,
            method=search_method,
            auth_config=auth_config,
            response_mapping=response_mapping,
        )

        # Step 7: Validate config by creating provider and testing
        logger.info("Validating generated config")
        self._validate_config(config, api_key, test_query)

        logger.info(f"Successfully generated config for '{provider_name}'")
        return config

    def _determine_auth_config(self, spec: OpenAPISpec) -> dict[str, Any]:
        """Determine authentication configuration from spec.

        Args:
            spec: Parsed OpenAPI specification

        Returns:
            Auth configuration dict

        Raises:
            ConfigError: If no supported auth scheme found
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
            RunError: If request fails
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
                    url,
                    params={"query": query, "limit": 5},
                    headers=headers,
                    timeout=timeout,
                )
            else:
                raise RunError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise RunError(f"Test query failed: {e}") from e

    def _build_config(
        self,
        provider_name: str,
        base_url: str,
        endpoint: str,
        method: str,
        auth_config: dict,
        response_mapping: dict,
    ) -> dict[str, Any]:
        """Build complete provider configuration.

        Args:
            provider_name: Name for the provider
            base_url: API base URL
            endpoint: Endpoint path
            method: HTTP method
            auth_config: Auth configuration
            response_mapping: Response mapping configuration

        Returns:
            Complete config dict
        """
        return {
            provider_name: {
                "tool": "openapi",
                "api_key_env": f"{provider_name.upper()}_API_KEY",
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

    def _validate_config(self, config: dict, api_key: str, test_query: str) -> None:
        """Validate configuration by creating provider and testing.

        Args:
            config: Generated configuration
            api_key: API key for testing
            test_query: Test query string

        Raises:
            ConfigError: If config is invalid
            RunError: If test query fails
        """
        # Extract provider name and config
        provider_name = list(config.keys())[0]
        provider_config = config[provider_name]

        # Create provider with test credentials
        # Update config with actual API key for testing
        test_config = provider_config.copy()
        test_config["options"]["api_key"] = api_key

        try:
            provider = OpenAPIProvider(test_config["options"])
        except Exception as e:
            raise ConfigError(f"Invalid configuration: {e}") from e

        # Execute test query
        try:
            results = provider.search(test_query, top_k=5)
            logger.info(f"Validation successful: got {len(results)} results")

            if not results:
                logger.warning("Test query returned no results")

        except Exception as e:
            raise RunError(f"Test query failed: {e}") from e
