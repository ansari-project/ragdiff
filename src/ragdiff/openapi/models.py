"""Data models for OpenAPI specification parsing."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EndpointInfo:
    """Information about a single API endpoint.

    Represents a single operation (path + method) from an OpenAPI spec.
    """

    path: str
    """API path (e.g., /v1/search)"""

    method: str
    """HTTP method (GET, POST, PUT, DELETE, etc.)"""

    summary: Optional[str] = None
    """Brief summary of endpoint purpose"""

    description: Optional[str] = None
    """Detailed description of endpoint"""

    operation_id: Optional[str] = None
    """Unique operation identifier"""

    parameters: list[dict[str, Any]] = field(default_factory=list)
    """List of parameter definitions (query, path, header, cookie)"""

    request_body_schema: Optional[dict[str, Any]] = None
    """JSON schema for request body (if applicable)"""

    response_schema: Optional[dict[str, Any]] = None
    """JSON schema for successful response (200/201)"""

    tags: list[str] = field(default_factory=list)
    """Tags/categories for grouping endpoints"""

    def __str__(self) -> str:
        """String representation of endpoint."""
        summary = f" - {self.summary}" if self.summary else ""
        return f"{self.method.upper()} {self.path}{summary}"


@dataclass
class AuthScheme:
    """Information about an authentication scheme.

    Represents a security scheme from components.securitySchemes.
    """

    name: str
    """Scheme name (as defined in spec)"""

    type: str
    """Scheme type (apiKey, http, oauth2, openIdConnect)"""

    scheme: Optional[str] = None
    """HTTP authentication scheme (bearer, basic, etc.) - for type=http"""

    bearer_format: Optional[str] = None
    """Format hint for bearer tokens (e.g., JWT)"""

    location: Optional[str] = None
    """Location of API key (query, header, cookie) - for type=apiKey"""

    parameter_name: Optional[str] = None
    """Parameter name for API key - for type=apiKey"""

    flows: Optional[dict[str, Any]] = None
    """OAuth2 flows configuration - for type=oauth2"""

    openid_connect_url: Optional[str] = None
    """OpenID Connect discovery URL - for type=openIdConnect"""

    description: Optional[str] = None
    """Description of auth scheme"""

    def __str__(self) -> str:
        """String representation of auth scheme."""
        if self.type == "http":
            return f"{self.name}: HTTP {self.scheme or 'auth'}"
        elif self.type == "apiKey":
            return f"{self.name}: API Key in {self.location} ({self.parameter_name})"
        else:
            return f"{self.name}: {self.type}"


@dataclass
class OpenAPIInfo:
    """General information about the API from OpenAPI spec.

    Represents the info object and server details.
    """

    title: str
    """API title"""

    version: str
    """API version"""

    description: Optional[str] = None
    """API description"""

    openapi_version: str = "3.0.0"
    """OpenAPI specification version"""

    servers: list[dict[str, Any]] = field(default_factory=list)
    """Server configurations"""

    contact: Optional[dict[str, Any]] = None
    """Contact information"""

    license: Optional[dict[str, Any]] = None
    """License information"""

    def get_base_url(self) -> Optional[str]:
        """Get the first server URL, if available.

        Returns:
            Base URL string or None if no servers defined
        """
        if self.servers:
            return self.servers[0].get("url")
        return None

    def __str__(self) -> str:
        """String representation of API info."""
        return f"{self.title} v{self.version} (OpenAPI {self.openapi_version})"
