# Specification: Multi-Tenant Credential Support

**ID**: 0004
**Created**: 2025-10-21
**Status**: Draft
**Protocol**: SPIDER

---

## Problem Statement

The current RAGDiff API requires all secrets to be loaded from the process environment variables, which prevents use in multi-tenant environments where different API requests need different credentials.

### Current Limitation

```python
# ❌ PROBLEM: All tenants share the same environment
os.environ['VECTARA_API_KEY'] = 'tenant_a_key'
results = query("config.yaml", "query for tenant A", tool="vectara")

# This would affect ALL subsequent requests in the process!
os.environ['VECTARA_API_KEY'] = 'tenant_b_key'
results = query("config.yaml", "query for tenant B", tool="vectara")
```

### Use Cases

#### 1. Multi-Tenant SaaS Application
```python
# FastAPI endpoint serving multiple customers
@app.post("/api/search")
async def search(request: SearchRequest, tenant_id: str):
    # Each tenant has their own RAG credentials
    tenant_creds = get_tenant_credentials(tenant_id)

    # Need to pass credentials per-request
    results = query(
        "config.yaml",
        request.query,
        tool="vectara",
        credentials=tenant_creds  # ❌ Not currently possible
    )
```

#### 2. Dynamic Configuration
```python
# Load config from database instead of YAML file
config_dict = {
    "tools": {
        "vectara": {
            "api_key": "actual_key_value",  # ❌ Not currently supported
            "corpus_id": "my_corpus"
        }
    }
}

results = query(
    config_dict,  # ❌ Must be file path currently
    "What is RAG?",
    tool="vectara"
)
```

#### 3. Temporary Credentials
```python
# Use short-lived credentials from OAuth/STS
temp_creds = get_temporary_credentials()

results = query(
    "config.yaml",
    "search query",
    tool="vectara",
    credentials={
        "VECTARA_API_KEY": temp_creds.access_token  # ❌ Not supported
    }
)
```

## Proposed Solution

Enable passing credentials and configuration as dictionaries at runtime, with environment variables as fallback.

### Design Principles

1. **Backward Compatible**: Existing code continues to work unchanged
2. **Explicit Over Implicit**: Passed credentials take precedence over environment
3. **Thread-Safe**: Per-request credentials don't affect other requests
4. **Secure**: No credential leakage between requests
5. **Flexible**: Support both YAML files and config dicts

### API Design

#### Primary Approach: Config Object with Credentials (Selected)

Create Config objects with credentials, then pass Config to API functions:

```python
# Step 1: Load config with tenant credentials
config = load_config(
    "config.yaml",
    credentials={
        "VECTARA_API_KEY": tenant_api_key,
        "ANTHROPIC_API_KEY": tenant_llm_key
    }
)

# Step 2: Use config object in API functions
results = query(config, "What is RAG?", tool="vectara")

# Can also accept dict config
config_dict = {
    "tools": {
        "vectara": {
            "api_key_env": "VECTARA_API_KEY",
            "corpus_id": "my_corpus"
        }
    }
}
config = load_config(
    config_dict,
    credentials={"VECTARA_API_KEY": "sk_abc123"}
)
results = query(config, "query", tool="vectara")
```

**Benefits of This Approach:**
- Clear separation: config loading vs query execution
- Config object can be validated once, reused for multiple queries
- Easier to test and reason about
- Credentials are encapsulated in Config object

#### Updated API Signatures

```python
def load_config(
    config: str | Path | dict,  # File path OR dict
    credentials: Optional[dict[str, str]] = None,  # NEW
) -> Config:
    """Load and validate configuration.

    Args:
        config: Path to YAML file OR config dictionary
        credentials: Optional credential overrides (env var name -> value)

    Returns:
        Validated Config object with credentials

    Example:
        # From file with environment variables
        config = load_config("config.yaml")

        # From file with explicit credentials
        config = load_config("config.yaml", credentials={
            "VECTARA_API_KEY": "sk_abc123"
        })

        # From dict
        config = load_config({"tools": {...}}, credentials={...})
    """

def query(
    config: Config | str | Path,  # Accept Config OR path (backward compat)
    query_text: str,
    tool: str,
    top_k: int = 5,
) -> list[RagResult]:
    """Run a query against a RAG system.

    Args:
        config: Config object OR path to YAML file (backward compatible)
        query_text: The search query
        tool: Name of the RAG tool to query
        top_k: Number of results to return

    Example:
        # New: Config object with credentials
        config = load_config("config.yaml", credentials={...})
        results = query(config, "What is RAG?", tool="vectara")

        # Old: Still works for backward compatibility
        results = query("config.yaml", "What is RAG?", tool="vectara")
    """
```

### Implementation Strategy

#### 1. Update Config Class

```python
class Config:
    """Manages configuration for the comparison harness."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        config_dict: Optional[dict] = None,  # NEW
        credentials: Optional[dict[str, str]] = None,  # NEW
    ):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file
            config_dict: Configuration dictionary (alternative to file)
            credentials: Optional credential overrides (env var name -> value)

        Raises:
            ValueError: If both config_path and config_dict provided, or neither
        """
        if config_path and config_dict:
            raise ValueError("Provide either config_path or config_dict, not both")
        if not config_path and not config_dict:
            raise ValueError("Must provide either config_path or config_dict")

        self.config_path = config_path
        self._credentials = credentials or {}

        # Load from file or use provided dict
        if config_path:
            self._raw_config = self._load_config()
        else:
            self._raw_config = config_dict

        self._process_env_vars()
        self._parse_config()

    def _get_env_value(self, env_var_name: str) -> Optional[str]:
        """Get environment value from credentials or environment.

        Credentials dict takes precedence over environment variables.
        """
        # Check passed credentials first
        if env_var_name in self._credentials:
            return self._credentials[env_var_name]

        # Fall back to environment
        return os.getenv(env_var_name)
```

#### 2. Update Environment Variable Processing

```python
def _process_env_vars(self) -> None:
    """Process environment variable references in config."""

    def replace_env_vars(obj):
        """Recursively replace ${ENV_VAR} with actual values."""
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                # Use _get_env_value instead of os.getenv
                value = self._get_env_value(env_var)
                if value is None:
                    return obj
                return value
            return obj
        elif isinstance(obj, dict):
            return {k: replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_env_vars(item) for item in obj]
        return obj

    self._raw_config = replace_env_vars(self._raw_config)
```

#### 3. Update Adapter Base Class

```python
class RagAdapter(ABC):
    """Base class for all RAG adapters."""

    def __init__(self, config: ToolConfig, credentials: Optional[dict[str, str]] = None):
        """Initialize adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides
        """
        self.config = config
        self._credentials = credentials or {}
        self._validate_credentials()

    def _get_credential(self, env_var_name: str) -> Optional[str]:
        """Get credential from override dict or environment.

        Args:
            env_var_name: Name of environment variable

        Returns:
            Credential value or None
        """
        # Check credentials dict first
        if env_var_name in self._credentials:
            return self._credentials[env_var_name]

        # Fall back to environment
        return os.getenv(env_var_name)
```

#### 4. Update Adapters

```python
# Example: VectaraAdapter
class VectaraAdapter(RagAdapter):
    def __init__(self, config: ToolConfig, credentials: Optional[dict[str, str]] = None):
        super().__init__(config, credentials)

        # Use _get_credential instead of os.getenv
        api_key = self._get_credential(config.api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"Missing API key: {config.api_key_env}. "
                "Set environment variable or pass via credentials parameter."
            )

        self.api_key = api_key
        # ... rest of initialization
```

#### 5. Update Factory

```python
def create_adapter(
    tool_name: str,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,  # NEW
) -> RagAdapter:
    """Create an adapter instance from configuration.

    Args:
        tool_name: Display name for the adapter
        config: Tool configuration
        credentials: Optional credential overrides

    Returns:
        Configured adapter instance
    """
    adapter_name = config.adapter or tool_name

    if adapter_name not in _registry._adapters:
        available = ", ".join(_registry.list_adapters())
        raise ValueError(
            f"Unknown adapter: {adapter_name}. "
            f"Available adapters: {available}"
        )

    adapter_class = _registry.get(adapter_name)
    return adapter_class(config, credentials=credentials)  # Pass credentials
```

#### 6. Update API Functions

```python
def query(
    config: str | Path | dict,
    query_text: str,
    tool: str,
    top_k: int = 5,
    credentials: Optional[dict[str, str]] = None,
) -> list[RagResult]:
    """Run a query against a RAG system.

    Args:
        config: Path to YAML config file OR config dictionary
        query_text: The search query
        tool: Name of the RAG tool to query
        top_k: Number of results to return
        credentials: Optional credential overrides (env var name -> value)
    """
    _validate_query_text(query_text)
    _validate_top_k(top_k)

    # Load config from file or dict
    if isinstance(config, dict):
        cfg = Config(config_dict=config, credentials=credentials)
    else:
        path = _validate_config_path(config)
        cfg = Config(config_path=path, credentials=credentials)

    # Get tool config
    if tool not in cfg.tools:
        available = ", ".join(cfg.tools.keys())
        raise ConfigurationError(
            f"Tool '{tool}' not found in config. Available: {available}"
        )

    tool_config = cfg.tools[tool]

    # Create adapter with credentials
    adapter = create_adapter(tool, tool_config, credentials=credentials)

    # Execute query
    return adapter.search(query_text, top_k=top_k)
```

### Security Considerations

#### 1. Credential Isolation
```python
# Each request gets its own Config object
config_a = Config("config.yaml", credentials={"KEY": "tenant_a"})
config_b = Config("config.yaml", credentials={"KEY": "tenant_b"})

# No credential leakage between configs
assert config_a._credentials != config_b._credentials
```

#### 2. No Environment Pollution
```python
# Passed credentials DON'T modify os.environ
query("config.yaml", "query", tool="vectara", credentials={"KEY": "value"})

# Environment unchanged
assert "KEY" not in os.environ or os.environ["KEY"] != "value"
```

#### 3. Precedence Order
```
1. Passed credentials dict (highest priority)
2. Process environment variables
3. .env file (via load_dotenv)
4. Missing (raise error)
```

## Success Criteria

### Functional Requirements
- [ ] Accept `dict` as config parameter (not just file path)
- [ ] Accept `credentials` dict in all API functions
- [ ] Credentials dict takes precedence over environment
- [ ] Thread-safe: no shared mutable state
- [ ] Backward compatible: existing code works unchanged

### Non-Functional Requirements
- [ ] Zero performance overhead when credentials not used
- [ ] No credential leakage between requests
- [ ] Clear error messages for missing credentials
- [ ] Comprehensive documentation and examples

### Testing Requirements
- [ ] Unit tests for credential precedence
- [ ] Integration tests for multi-tenant scenarios
- [ ] Thread-safety tests with concurrent requests
- [ ] Backward compatibility tests

## Migration Path

### Phase 1: Add Optional Parameters (Backward Compatible)
```python
# Existing code works unchanged
results = query("config.yaml", "query", tool="vectara")

# New code can pass credentials
results = query("config.yaml", "query", tool="vectara", credentials={...})
```

### Phase 2: Documentation
- Update README with multi-tenant examples
- Add FastAPI multi-tenant example
- Update API reference docs

### Phase 3: Best Practices Guide
- Document credential management patterns
- Security best practices
- Performance considerations

## Open Questions

1. **Credential Naming**: Should credentials dict use:
   - Env var names: `{"VECTARA_API_KEY": "value"}` ✅ Recommended
   - Adapter fields: `{"api_key": "value"}` (requires mapping)

2. **Config Dict Format**: Should config dict match YAML structure exactly?
   - Yes, 1:1 mapping with YAML ✅ Recommended
   - Or provide programmatic builder API?

3. **Validation**: When to validate credentials?
   - At Config creation ✅ Fail fast
   - At adapter creation (lazy)
   - Both?

4. **Caching**: Should Config objects be cacheable?
   - No, credentials may change per request ✅ Recommended
   - Yes, with cache key including credentials hash

## Examples

### Example 1: Multi-Tenant FastAPI

```python
from fastapi import FastAPI, Depends
from ragdiff import query

app = FastAPI()

def get_tenant_credentials(tenant_id: str) -> dict[str, str]:
    """Fetch tenant-specific credentials from database."""
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    return {
        "VECTARA_API_KEY": tenant.vectara_key,
        "ANTHROPIC_API_KEY": tenant.anthropic_key,
    }

@app.post("/api/search")
async def search(
    request: SearchRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Search endpoint with per-tenant credentials."""
    creds = get_tenant_credentials(tenant_id)

    results = query(
        "config.yaml",
        request.query,
        tool="vectara",
        top_k=request.top_k,
        credentials=creds  # Per-request credentials
    )

    return {"results": [r.to_dict() for r in results]}
```

### Example 2: Dynamic Configuration

```python
from ragdiff import query

# Build config programmatically
config = {
    "tools": {
        "vectara": {
            "api_key_env": "VECTARA_API_KEY",
            "corpus_id": "my_corpus",
            "base_url": "https://api.vectara.io"
        }
    }
}

# Pass both config dict and credentials
results = query(
    config,  # Dict instead of file path
    "What is RAG?",
    tool="vectara",
    credentials={"VECTARA_API_KEY": "sk_abc123"}
)
```

### Example 3: Temporary Credentials

```python
from ragdiff import compare
import boto3

# Get temporary credentials from AWS STS
sts = boto3.client('sts')
temp_creds = sts.assume_role(
    RoleArn='arn:aws:iam::123456789012:role/RagAccess',
    RoleSessionName='rag-session'
)

# Use temporary credentials
comparison = compare(
    "config.yaml",
    "search query",
    tools=["vectara", "goodmem"],
    credentials={
        "VECTARA_API_KEY": temp_creds['Credentials']['AccessKeyId'],
        # ... other temp credentials
    }
)
```

## Implementation Plan

See [codev/plans/0004-multi-tenant-credentials.md](../plans/0004-multi-tenant-credentials.md) for detailed implementation steps.

## References

- **Issue**: Multi-tenant credential management
- **Related**: [0003-library-refactoring.md](0003-library-refactoring.md)
- **Security**: Follow principle of least privilege
