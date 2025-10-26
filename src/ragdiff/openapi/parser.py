"""OpenAPI specification parser.

Fetches and parses OpenAPI 3.x specifications from URLs or files.
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

from ..core.errors import ConfigurationError
from .models import AuthScheme, EndpointInfo, OpenAPIInfo

logger = logging.getLogger(__name__)


class OpenAPISpec:
    """Parsed OpenAPI specification.

    Supports fetching specs from URLs, parsing JSON/YAML,
    and extracting structured information about endpoints and auth.

    Example:
        # From URL
        spec = OpenAPISpec.from_url("https://api.example.com/openapi.json")

        # From file
        spec = OpenAPISpec.from_file("openapi.yaml")

        # Access information
        endpoints = spec.get_endpoints()
        auth_schemes = spec.get_auth_schemes()
        info = spec.get_info()
    """

    def __init__(self, spec_dict: dict[str, Any]):
        """Initialize from parsed OpenAPI spec dictionary.

        Args:
            spec_dict: Parsed OpenAPI specification (JSON/YAML as dict)

        Raises:
            ConfigurationError: If spec is invalid or unsupported version
        """
        self.spec = spec_dict

        # Validate OpenAPI version
        openapi_version = spec_dict.get("openapi", "")
        if not openapi_version.startswith("3."):
            raise ConfigurationError(
                f"Unsupported OpenAPI version: {openapi_version}. "
                "Only OpenAPI 3.x is supported."
            )

        self.openapi_version = openapi_version
        logger.info(f"Loaded OpenAPI spec version {openapi_version}")

    @classmethod
    def from_url(cls, url: str, timeout: int = 30) -> "OpenAPISpec":
        """Fetch and parse OpenAPI spec from URL.

        Handles common OpenAPI spec locations:
        - Direct spec URL (e.g., /openapi.json, /openapi.yaml)
        - Swagger UI URLs (tries /openapi.json, /swagger.json)

        Args:
            url: URL to OpenAPI specification
            timeout: Request timeout in seconds

        Returns:
            Parsed OpenAPISpec instance

        Raises:
            ConfigurationError: If spec cannot be fetched or parsed
        """
        logger.info(f"Fetching OpenAPI spec from {url}")

        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ConfigurationError(f"Failed to fetch OpenAPI spec from {url}: {e}") from e

        # Determine format (JSON or YAML) from content-type or URL
        content_type = response.headers.get("content-type", "").lower()

        try:
            if "json" in content_type or url.endswith(".json"):
                spec_dict = response.json()
            elif "yaml" in content_type or url.endswith((".yaml", ".yml")):
                spec_dict = yaml.safe_load(response.text)
            else:
                # Try JSON first, fallback to YAML
                try:
                    spec_dict = response.json()
                except json.JSONDecodeError:
                    spec_dict = yaml.safe_load(response.text)

        except Exception as e:
            raise ConfigurationError(f"Failed to parse OpenAPI spec: {e}") from e

        return cls(spec_dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "OpenAPISpec":
        """Load and parse OpenAPI spec from local file.

        Args:
            path: Path to OpenAPI specification file (JSON or YAML)

        Returns:
            Parsed OpenAPISpec instance

        Raises:
            ConfigurationError: If file cannot be read or parsed
        """
        path_obj = Path(path)

        if not path_obj.exists():
            raise ConfigurationError(f"OpenAPI spec file not found: {path}")

        logger.info(f"Loading OpenAPI spec from {path}")

        try:
            content = path_obj.read_text()

            # Determine format from extension
            if path_obj.suffix == ".json":
                spec_dict = json.loads(content)
            elif path_obj.suffix in (".yaml", ".yml"):
                spec_dict = yaml.safe_load(content)
            else:
                # Try JSON first, fallback to YAML
                try:
                    spec_dict = json.loads(content)
                except json.JSONDecodeError:
                    spec_dict = yaml.safe_load(content)

        except Exception as e:
            raise ConfigurationError(f"Failed to parse OpenAPI spec from {path}: {e}") from e

        return cls(spec_dict)

    def get_info(self) -> OpenAPIInfo:
        """Extract general API information.

        Returns:
            OpenAPIInfo with title, version, description, etc.
        """
        info_obj = self.spec.get("info", {})
        servers = self.spec.get("servers", [])

        return OpenAPIInfo(
            title=info_obj.get("title", "Untitled API"),
            version=info_obj.get("version", "1.0.0"),
            description=info_obj.get("description"),
            openapi_version=self.openapi_version,
            servers=servers,
            contact=info_obj.get("contact"),
            license=info_obj.get("license"),
        )

    def get_endpoints(self) -> list[EndpointInfo]:
        """Extract all API endpoints from specification.

        Returns:
            List of EndpointInfo objects, one per path+method combination
        """
        paths = self.spec.get("paths", {})
        endpoints = []

        for path, path_item in paths.items():
            # Skip $ref and other non-method keys
            if not isinstance(path_item, dict):
                continue

            # Iterate through HTTP methods
            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                operation = path_item.get(method)
                if not operation or not isinstance(operation, dict):
                    continue

                # Extract endpoint information
                endpoint = EndpointInfo(
                    path=path,
                    method=method.upper(),
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    operation_id=operation.get("operationId"),
                    parameters=operation.get("parameters", []),
                    request_body_schema=self._extract_request_body_schema(operation),
                    response_schema=self._extract_response_schema(operation),
                    tags=operation.get("tags", []),
                )

                endpoints.append(endpoint)

        logger.info(f"Found {len(endpoints)} endpoints in OpenAPI spec")
        return endpoints

    def get_endpoint(self, path: str, method: str) -> Optional[EndpointInfo]:
        """Get specific endpoint by path and method.

        Args:
            path: API path (e.g., /v1/search)
            method: HTTP method (case insensitive)

        Returns:
            EndpointInfo if found, None otherwise
        """
        method_lower = method.lower()
        paths = self.spec.get("paths", {})

        path_item = paths.get(path)
        if not path_item or not isinstance(path_item, dict):
            return None

        operation = path_item.get(method_lower)
        if not operation or not isinstance(operation, dict):
            return None

        return EndpointInfo(
            path=path,
            method=method.upper(),
            summary=operation.get("summary"),
            description=operation.get("description"),
            operation_id=operation.get("operationId"),
            parameters=operation.get("parameters", []),
            request_body_schema=self._extract_request_body_schema(operation),
            response_schema=self._extract_response_schema(operation),
            tags=operation.get("tags", []),
        )

    def get_auth_schemes(self) -> list[AuthScheme]:
        """Extract authentication schemes from specification.

        Returns:
            List of AuthScheme objects from components.securitySchemes
        """
        components = self.spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        auth_schemes = []
        for name, scheme_obj in security_schemes.items():
            if not isinstance(scheme_obj, dict):
                continue

            scheme_type = scheme_obj.get("type")
            if not scheme_type:
                continue

            auth_scheme = AuthScheme(
                name=name,
                type=scheme_type,
                scheme=scheme_obj.get("scheme"),
                bearer_format=scheme_obj.get("bearerFormat"),
                location=scheme_obj.get("in"),
                parameter_name=scheme_obj.get("name"),
                flows=scheme_obj.get("flows"),
                openid_connect_url=scheme_obj.get("openIdConnectUrl"),
                description=scheme_obj.get("description"),
            )

            auth_schemes.append(auth_scheme)

        logger.info(f"Found {len(auth_schemes)} auth schemes in OpenAPI spec")
        return auth_schemes

    def _extract_request_body_schema(self, operation: dict) -> Optional[dict[str, Any]]:
        """Extract request body schema from operation.

        Args:
            operation: Operation object from OpenAPI spec

        Returns:
            Schema dict or None if no request body
        """
        request_body = operation.get("requestBody")
        if not request_body or not isinstance(request_body, dict):
            return None

        content = request_body.get("content", {})

        # Try to get JSON schema (most common)
        for content_type in ["application/json", "application/x-www-form-urlencoded"]:
            if content_type in content:
                media_type = content[content_type]
                return media_type.get("schema")

        # Return first available schema
        for media_type in content.values():
            if isinstance(media_type, dict) and "schema" in media_type:
                return media_type["schema"]

        return None

    def _extract_response_schema(self, operation: dict) -> Optional[dict[str, Any]]:
        """Extract response schema from operation (200/201 responses).

        Args:
            operation: Operation object from OpenAPI spec

        Returns:
            Schema dict or None if no success response
        """
        responses = operation.get("responses", {})

        # Try successful response codes
        for status_code in ["200", "201", "default"]:
            response = responses.get(status_code)
            if not response or not isinstance(response, dict):
                continue

            content = response.get("content", {})

            # Try to get JSON schema
            for content_type in ["application/json", "*/*"]:
                if content_type in content:
                    media_type = content[content_type]
                    if isinstance(media_type, dict) and "schema" in media_type:
                        return media_type["schema"]

            # Return first available schema
            for media_type in content.values():
                if isinstance(media_type, dict) and "schema" in media_type:
                    return media_type["schema"]

        return None
