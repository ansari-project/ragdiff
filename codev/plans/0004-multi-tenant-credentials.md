# Implementation Plan: Multi-Tenant Credential Support

**ID**: 0004
**Spec**: [0004-multi-tenant-credentials.md](../specs/0004-multi-tenant-credentials.md)
**Created**: 2025-10-21
**Status**: Ready for Implementation
**Protocol**: SPIDER

---

## Overview

Implement multi-tenant credential support using the **Config Object with Credentials** approach, enabling different API requests to use different credentials without environment variable pollution.

## Design Summary

**Selected Approach**: Config Object with Credentials

```python
# Create config with tenant-specific credentials
config = load_config("config.yaml", credentials={"VECTARA_API_KEY": tenant_key})

# Pass config to API functions
results = query(config, "What is RAG?", tool="vectara")
```

**Key Principles**:
1. Credentials passed at config load time, encapsulated in Config object
2. Config object passed to API functions (not file paths)
3. Backward compatible: file paths still work
4. Thread-safe: no shared mutable state

## Implementation Phases

### Phase 1: Core Infrastructure
Update Config class and credential resolution mechanism.

### Phase 2: Adapter Updates
Update adapters to use credential resolution from Config.

### Phase 3: API Updates
Update API functions to accept Config objects.

### Phase 4: Testing
Add comprehensive tests for multi-tenant scenarios.

### Phase 5: Documentation
Update docs with multi-tenant examples.

---

## Phase 1: Core Infrastructure

### Step 1.1: Update Config Class Constructor

**File**: `src/ragdiff/core/config.py`

**Changes**:
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
                Takes precedence over environment variables.

        Raises:
            ValueError: If both config_path and config_dict provided, or neither
        """
        # Validation
        if config_path and config_dict:
            raise ValueError("Provide either config_path or config_dict, not both")
        if not config_path and not config_dict:
            # Default to standard location if neither provided
            config_path = Path(__file__).parent.parent.parent / "configs" / "tools.yaml"

        self.config_path = config_path
        self._credentials = credentials or {}

        # Load from file or use provided dict
        if config_path:
            self._raw_config = self._load_config()
        else:
            self._raw_config = config_dict

        self._process_env_vars()
        self._parse_config()
```

**Rationale**: Accept dict config and credentials, validate mutually exclusive inputs.

### Step 1.2: Add Credential Resolution Method

**File**: `src/ragdiff/core/config.py`

**Add new method**:
```python
def _get_env_value(self, env_var_name: str) -> Optional[str]:
    """Get environment value from credentials or environment.

    Credentials dict takes precedence over environment variables.

    Args:
        env_var_name: Name of environment variable

    Returns:
        Value from credentials dict, environment, or None

    Resolution order:
        1. Passed credentials dict (highest priority)
        2. Process environment variables
        3. .env file (via load_dotenv)
        4. None (will cause error during validation)
    """
    # Check passed credentials first
    if env_var_name in self._credentials:
        return self._credentials[env_var_name]

    # Fall back to environment
    return os.getenv(env_var_name)
```

**Rationale**: Centralize credential resolution with clear precedence order.

### Step 1.3: Update Environment Variable Processing

**File**: `src/ragdiff/core/config.py`

**Modify `_process_env_vars` method**:
```python
def _process_env_vars(self) -> None:
    """Process environment variable references in config."""

    def replace_env_vars(obj):
        """Recursively replace ${ENV_VAR} with actual values."""
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                # Use _get_env_value instead of os.getenv
                value = self._get_env_value(env_var)  # CHANGED
                if value is None:
                    # Keep the placeholder if env var not set
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

**Rationale**: Use credential resolution for ${ENV_VAR} substitutions.

### Step 1.4: Update Validation Method

**File**: `src/ragdiff/core/config.py`

**Modify `validate` method**:
```python
def validate(self) -> None:
    """Validate the configuration.

    Raises:
        ValueError: If configuration is invalid
    """
    # Check that at least one tool is configured
    if not self.tools:
        raise ValueError("No tools configured")

    # Validate each configured tool
    for _tool_name, config in self.tools.items():
        # Check API key is set in environment OR credentials
        if not self._get_env_value(config.api_key_env):  # CHANGED
            raise ValueError(
                f"Missing required environment variable: {config.api_key_env}. "
                f"Set it in environment or pass via credentials parameter."
            )

    # Check LLM config if present (optional)
    llm_config = self.get_llm_config()
    if llm_config and llm_config.get("api_key_env"):
        if not self._get_env_value(llm_config["api_key_env"]):  # CHANGED
            logger.warning(
                f"LLM evaluation configured but API key not set: {llm_config['api_key_env']}"
            )
```

**Rationale**: Validate credentials from both sources.

---

## Phase 2: Adapter Updates

### Step 2.1: Update RagAdapter Base Class

**File**: `src/ragdiff/adapters/base.py`

**Add credential resolution to base class**:
```python
from typing import Optional

class RagAdapter(ABC):
    """Base class for all RAG adapters."""

    # API version this adapter implements
    ADAPTER_API_VERSION = "1.0.0"

    def __init__(
        self,
        config: ToolConfig,
        credentials: Optional[dict[str, str]] = None,  # NEW
    ):
        """Initialize the adapter.

        Args:
            config: Tool configuration
            credentials: Optional credential overrides (env var name -> value)
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

        Resolution order:
            1. Passed credentials dict
            2. Environment variables
        """
        # Check credentials dict first
        if env_var_name in self._credentials:
            return self._credentials[env_var_name]

        # Fall back to environment
        return os.getenv(env_var_name)

    def _validate_credentials(self) -> None:
        """Validate required credentials are available."""
        if not self._get_credential(self.config.api_key_env):  # CHANGED
            raise ValueError(
                f"Missing required environment variable: {self.config.api_key_env}\n"
                f"Please set it with your {self.config.name} API key or pass via credentials."
            )
```

**Rationale**: Provide credential resolution in base class for all adapters to use.

### Step 2.2: Update VectaraAdapter

**File**: `src/ragdiff/adapters/vectara.py`

**Modify `__init__` method**:
```python
def __init__(
    self,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,  # NEW
):
    """Initialize Vectara adapter.

    Args:
        config: Tool configuration
        credentials: Optional credential overrides
    """
    super().__init__(config, credentials)  # CHANGED: pass credentials

    # Get credentials from override or environment
    api_key = self._get_credential(config.api_key_env)  # CHANGED
    if not api_key:
        raise ConfigurationError(
            f"Missing API key environment variable: {config.api_key_env}"
        )

    self.api_key = api_key
    self.base_url = config.base_url or "https://api.vectara.io"
    # ... rest of initialization
```

**Rationale**: Use base class credential resolution.

### Step 2.3: Update GoodmemAdapter

**File**: `src/ragdiff/adapters/goodmem.py`

**Same changes as VectaraAdapter**:
```python
def __init__(
    self,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,  # NEW
):
    super().__init__(config, credentials)  # CHANGED

    api_key = self._get_credential(config.api_key_env)  # CHANGED
    if not api_key:
        raise ConfigurationError(
            f"Missing API key environment variable: {config.api_key_env}"
        )

    self.api_key = api_key
    # ... rest
```

### Step 2.4: Update AgentsetAdapter

**File**: `src/ragdiff/adapters/agentset.py`

**Same pattern, but handles two env vars**:
```python
def __init__(
    self,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,  # NEW
):
    super().__init__(config, credentials)  # CHANGED

    # Get API credentials
    api_token = self._get_credential(config.api_key_env)  # CHANGED
    if not api_token:
        raise ConfigurationError(
            f"Missing required environment variable: {config.api_key_env}"
        )

    # Get namespace ID
    namespace_id_env = config.namespace_id_env
    if not namespace_id_env:
        raise ConfigurationError("namespace_id_env not configured")

    namespace_id = self._get_credential(namespace_id_env)  # CHANGED
    if not namespace_id:
        raise ConfigurationError(
            f"Missing required environment variable: {namespace_id_env}"
        )

    # Initialize client
    self.client = AgentsetClient(api_token=api_token, namespace_id=namespace_id)
    # ... rest
```

### Step 2.5: Update Adapter validate_config Methods

**Files**: All adapters with `validate_config` static methods

**Example** (`vectara.py`):
```python
@staticmethod
def validate_config(config: dict[str, Any]) -> None:
    """Validate adapter configuration.

    NOTE: This validates config structure only. Credential validation
    happens at adapter initialization time.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigurationError: If configuration is invalid
    """
    required = ["api_key_env"]
    for field in required:
        if field not in config:
            raise ConfigurationError(f"Missing required field: {field}")

    # Don't validate env var exists here - will be checked during init
    # This allows credentials to be passed later
```

**Rationale**: Separate config structure validation from credential validation.

---

## Phase 3: API Updates

### Step 3.1: Update load_config Function

**File**: `src/ragdiff/api.py`

**Add new function**:
```python
def load_config(
    config: str | Path | dict,
    credentials: Optional[dict[str, str]] = None,
) -> Config:
    """Load and validate configuration.

    Args:
        config: Path to YAML file OR config dictionary
        credentials: Optional credential overrides (env var name -> value)
            Takes precedence over environment variables.

    Returns:
        Validated Config object

    Raises:
        ConfigurationError: If config is invalid

    Example:
        # From file with environment variables
        config = load_config("config.yaml")

        # From file with explicit credentials
        config = load_config("config.yaml", credentials={
            "VECTARA_API_KEY": "sk_abc123"
        })

        # From dict
        config_dict = {"tools": {"vectara": {...}}}
        config = load_config(config_dict, credentials={...})
    """
    if isinstance(config, dict):
        cfg = Config(config_dict=config, credentials=credentials)
    else:
        path = _validate_config_path(config)
        cfg = Config(config_path=path, credentials=credentials)

    cfg.validate()
    return cfg
```

**Rationale**: Provide unified config loading with credential support.

### Step 3.2: Update query Function

**File**: `src/ragdiff/api.py`

**Modify signature and implementation**:
```python
def query(
    config: Config | str | Path,  # CHANGED: accept Config object
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

    Returns:
        List of RagResult objects

    Raises:
        ConfigurationError: If config is invalid or tool not found
        ValidationError: If parameters are invalid
        AdapterError: If query execution fails

    Example:
        # New: Config object with credentials
        config = load_config("config.yaml", credentials={...})
        results = query(config, "What is RAG?", tool="vectara")

        # Old: Still works for backward compatibility
        results = query("config.yaml", "What is RAG?", tool="vectara")
    """
    _validate_query_text(query_text)
    _validate_top_k(top_k)

    # Handle both Config objects and paths (backward compat)
    if isinstance(config, Config):
        cfg = config
    else:
        cfg = load_config(config)  # Load without credentials

    # Get tool config
    if tool not in cfg.tools:
        available = ", ".join(cfg.tools.keys())
        raise ConfigurationError(
            f"Tool '{tool}' not found in config. Available: {available}"
        )

    tool_config = cfg.tools[tool]

    # Create adapter with credentials from Config
    adapter = create_adapter(tool, tool_config, credentials=cfg._credentials)

    # Execute query
    return adapter.search(query_text, top_k=top_k)
```

**Rationale**: Accept Config objects while maintaining backward compatibility with paths.

### Step 3.3: Update compare Function

**File**: `src/ragdiff/api.py`

**Same pattern as query**:
```python
def compare(
    config: Config | str | Path,  # CHANGED
    query_text: str,
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> ComparisonResult:
    """Compare multiple RAG systems on a single query.

    Args:
        config: Config object OR path to YAML file
        query_text: The search query
        tools: List of tool names (None = all tools)
        top_k: Number of results per tool
        parallel: Run searches in parallel
        evaluate: Run LLM evaluation

    Example:
        config = load_config("config.yaml", credentials={...})
        result = compare(config, "query", tools=["vectara", "goodmem"])
    """
    _validate_query_text(query_text)
    _validate_top_k(top_k)

    # Handle Config objects and paths
    if isinstance(config, Config):
        cfg = config
    else:
        cfg = load_config(config)

    # Rest of implementation uses cfg._credentials
    # ...
```

### Step 3.4: Update run_batch Function

**File**: `src/ragdiff/api.py`

**Same pattern**:
```python
def run_batch(
    config: Config | str | Path,  # CHANGED
    queries: list[str],
    tools: Optional[list[str]] = None,
    top_k: int = 5,
    parallel: bool = True,
    evaluate: bool = False,
) -> list[ComparisonResult]:
    """Run multiple queries against multiple RAG systems."""
    # Same Config handling as compare
```

### Step 3.5: Update Adapter Factory

**File**: `src/ragdiff/adapters/factory.py`

**Add credentials parameter**:
```python
def create_adapter(
    tool_name: str,
    config: ToolConfig,
    credentials: Optional[dict[str, str]] = None,  # NEW
) -> RagAdapter:
    """Create an adapter instance from configuration.

    Args:
        tool_name: Display name for the adapter (from YAML key)
        config: Tool configuration
        credentials: Optional credential overrides

    Returns:
        Configured adapter instance

    Raises:
        ValueError: If adapter type is not registered
    """
    adapter_name = config.adapter or tool_name

    if adapter_name not in _registry._adapters:
        available = ", ".join(_registry.list_adapters())
        raise ValueError(
            f"Unknown adapter: {adapter_name}. "
            f"Available adapters: {available}"
        )

    adapter_class = _registry.get(adapter_name)
    return adapter_class(config, credentials=credentials)  # CHANGED
```

---

## Phase 4: Testing

### Step 4.1: Test Config with Credentials

**File**: `tests/test_config_credentials.py` (NEW)

```python
"""Tests for multi-tenant credential support."""

import os
import pytest
from pathlib import Path

from ragdiff.core.config import Config
from ragdiff.core.errors import ConfigurationError


def test_config_with_credentials_dict():
    """Test Config accepts credentials dict."""
    config_dict = {
        "tools": {
            "vectara": {
                "api_key_env": "VECTARA_API_KEY",
                "corpus_id": "test_corpus"
            }
        }
    }

    config = Config(
        config_dict=config_dict,
        credentials={"VECTARA_API_KEY": "test_key_123"}
    )

    # Credential should be available via _get_env_value
    assert config._get_env_value("VECTARA_API_KEY") == "test_key_123"


def test_credentials_precedence_over_environment():
    """Test credentials dict takes precedence over environment."""
    # Set environment variable
    os.environ["TEST_API_KEY"] = "env_value"

    config_dict = {
        "tools": {
            "test_tool": {
                "api_key_env": "TEST_API_KEY",
                "corpus_id": "test"
            }
        }
    }

    # Pass different value in credentials
    config = Config(
        config_dict=config_dict,
        credentials={"TEST_API_KEY": "cred_value"}
    )

    # Credentials should win
    assert config._get_env_value("TEST_API_KEY") == "cred_value"

    # Cleanup
    del os.environ["TEST_API_KEY"]


def test_env_var_substitution_with_credentials():
    """Test ${ENV_VAR} substitution uses credentials."""
    config_dict = {
        "tools": {
            "vectara": {
                "api_key_env": "VECTARA_API_KEY",
                "corpus_id": "${CORPUS_ID}"  # Will be substituted
            }
        }
    }

    config = Config(
        config_dict=config_dict,
        credentials={
            "VECTARA_API_KEY": "key123",
            "CORPUS_ID": "my_corpus"
        }
    )

    # corpus_id should be substituted from credentials
    assert config.tools["vectara"].corpus_id == "my_corpus"


def test_validation_with_missing_credentials():
    """Test validation fails when credentials missing."""
    config_dict = {
        "tools": {
            "vectara": {
                "api_key_env": "MISSING_KEY",
                "corpus_id": "test"
            }
        }
    }

    config = Config(config_dict=config_dict)

    with pytest.raises(ValueError, match="Missing required environment variable: MISSING_KEY"):
        config.validate()


def test_config_path_and_dict_mutual_exclusion():
    """Test can't provide both path and dict."""
    with pytest.raises(ValueError, match="Provide either config_path or config_dict"):
        Config(
            config_path=Path("config.yaml"),
            config_dict={"tools": {}}
        )
```

### Step 4.2: Test Adapters with Credentials

**File**: `tests/test_adapter_credentials.py` (NEW)

```python
"""Tests for adapter credential resolution."""

import pytest
from ragdiff.adapters.vectara import VectaraAdapter
from ragdiff.core.models import ToolConfig
from ragdiff.core.errors import ConfigurationError


def test_adapter_uses_credentials():
    """Test adapter uses passed credentials."""
    config = ToolConfig(
        name="vectara",
        api_key_env="VECTARA_API_KEY",
        corpus_id="test_corpus"
    )

    # Should NOT raise - credentials provided
    adapter = VectaraAdapter(
        config,
        credentials={"VECTARA_API_KEY": "test_key"}
    )

    assert adapter.api_key == "test_key"


def test_adapter_fails_without_credentials():
    """Test adapter fails when credentials missing."""
    config = ToolConfig(
        name="vectara",
        api_key_env="MISSING_KEY",
        corpus_id="test"
    )

    with pytest.raises(ConfigurationError, match="Missing API key"):
        VectaraAdapter(config)
```

### Step 4.3: Test Multi-Tenant API Usage

**File**: `tests/test_multi_tenant_api.py` (NEW)

```python
"""Tests for multi-tenant API usage patterns."""

import pytest
from ragdiff import load_config, query
from ragdiff.core.models import ToolConfig


@pytest.fixture
def sample_config_dict():
    return {
        "tools": {
            "vectara": {
                "api_key_env": "VECTARA_API_KEY",
                "corpus_id": "test_corpus",
                "base_url": "https://api.vectara.io"
            }
        }
    }


def test_load_config_with_credentials(sample_config_dict):
    """Test load_config accepts credentials."""
    config = load_config(
        sample_config_dict,
        credentials={"VECTARA_API_KEY": "tenant_a_key"}
    )

    assert config._credentials["VECTARA_API_KEY"] == "tenant_a_key"


def test_multi_tenant_isolation(sample_config_dict):
    """Test different configs have isolated credentials."""
    config_a = load_config(
        sample_config_dict,
        credentials={"VECTARA_API_KEY": "tenant_a_key"}
    )

    config_b = load_config(
        sample_config_dict,
        credentials={"VECTARA_API_KEY": "tenant_b_key"}
    )

    # Configs should have different credentials
    assert config_a._credentials != config_b._credentials
    assert config_a._get_env_value("VECTARA_API_KEY") == "tenant_a_key"
    assert config_b._get_env_value("VECTARA_API_KEY") == "tenant_b_key"


def test_backward_compatibility_with_path(tmp_path):
    """Test old API still works with file paths."""
    # Create temporary config file
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
tools:
  vectara:
    api_key_env: VECTARA_API_KEY
    corpus_id: test_corpus
""")

    # Old usage should still work (will use environment)
    config = load_config(str(config_file))
    assert config.config_path == config_file
```

---

## Phase 5: Documentation

### Step 5.1: Update README

**File**: `README.md`

Add multi-tenant section:

```markdown
### Multi-Tenant Usage

For multi-tenant applications (e.g., SaaS products), pass credentials per-request:

#### Option 1: Load Config with Credentials

\`\`\`python
from ragdiff import load_config, query

# Each tenant has their own credentials
tenant_a_config = load_config(
    "config.yaml",
    credentials={
        "VECTARA_API_KEY": tenant_a_api_key,
        "ANTHROPIC_API_KEY": tenant_a_llm_key
    }
)

tenant_b_config = load_config(
    "config.yaml",
    credentials={
        "VECTARA_API_KEY": tenant_b_api_key,
        "ANTHROPIC_API_KEY": tenant_b_llm_key
    }
)

# Use tenant-specific configs
results_a = query(tenant_a_config, "query", tool="vectara")
results_b = query(tenant_b_config, "query", tool="vectara")
\`\`\`

#### Option 2: Dynamic Configuration

\`\`\`python
from ragdiff import load_config, query

# Build config from database
def get_tenant_config(tenant_id):
    tenant = db.get_tenant(tenant_id)
    return {
        "tools": {
            "vectara": {
                "api_key_env": "VECTARA_API_KEY",
                "corpus_id": tenant.corpus_id
            }
        }
    }

# Load with tenant credentials
config = load_config(
    get_tenant_config(tenant_id),
    credentials=get_tenant_credentials(tenant_id)
)

results = query(config, "search query", tool="vectara")
\`\`\`
```

### Step 5.2: Update FastAPI Example

**File**: `examples/fastapi_integration.py`

Add multi-tenant pattern:

```python
from typing import Dict
from fastapi import FastAPI, Depends, HTTPException
from ragdiff import load_config, query

app = FastAPI()

# Simulated tenant credential store
TENANT_CREDENTIALS: Dict[str, Dict[str, str]] = {
    "tenant_a": {
        "VECTARA_API_KEY": "tenant_a_key",
        "ANTHROPIC_API_KEY": "tenant_a_llm_key"
    },
    "tenant_b": {
        "VECTARA_API_KEY": "tenant_b_key",
        "ANTHROPIC_API_KEY": "tenant_b_llm_key"
    }
}

def get_tenant_id(request: Request) -> str:
    """Extract tenant ID from request (e.g., from auth token)."""
    # In production: decode JWT, check API key, etc.
    return request.headers.get("X-Tenant-ID", "tenant_a")

@app.post("/api/search")
async def search(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """Multi-tenant search endpoint."""
    # Get tenant-specific credentials
    tenant_creds = TENANT_CREDENTIALS.get(tenant_id)
    if not tenant_creds:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Load config with tenant credentials
    config = load_config(CONFIG_FILE, credentials=tenant_creds)

    # Execute query with tenant-specific config
    try:
        results = query(
            config,
            query_text=request.query,
            tool=request.tool,
            top_k=request.top_k
        )

        return {
            "tenant_id": tenant_id,
            "query": request.query,
            "results": [r.to_dict() for r in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking backward compatibility | HIGH | Accept both Config objects and paths in API functions |
| Credential leakage between requests | HIGH | Each Config object has isolated credentials dict |
| Performance overhead | MEDIUM | Credentials dict lookup is O(1), minimal overhead |
| Thread-safety issues | MEDIUM | Config objects are immutable after creation |

## Success Criteria

- [ ] Config accepts `credentials` dict parameter
- [ ] Config accepts `config_dict` parameter (not just file paths)
- [ ] Adapters use credential resolution from Config
- [ ] API functions accept Config objects
- [ ] Backward compatible: file paths still work
- [ ] All tests pass (existing + new multi-tenant tests)
- [ ] Documentation updated with examples
- [ ] FastAPI example shows multi-tenant pattern

## Testing Checklist

- [ ] Config with credentials dict
- [ ] Credential precedence (credentials > environment)
- [ ] ${ENV_VAR} substitution with credentials
- [ ] Adapter credential resolution
- [ ] Multi-tenant isolation (no leakage)
- [ ] Thread-safety with concurrent requests
- [ ] Backward compatibility with file paths
- [ ] Validation with missing credentials

## Implementation Order

1. **Phase 1**: Config class updates (Steps 1.1-1.4)
2. **Phase 2**: Adapter updates (Steps 2.1-2.5)
3. **Phase 3**: API updates (Steps 3.1-3.5)
4. **Run tests**: Ensure nothing breaks
5. **Phase 4**: Add new tests (Steps 4.1-4.3)
6. **Phase 5**: Update documentation (Steps 5.1-5.2)

## Estimated Effort

- Phase 1 (Config): 1-2 hours
- Phase 2 (Adapters): 1-2 hours
- Phase 3 (API): 1 hour
- Phase 4 (Testing): 2-3 hours
- Phase 5 (Docs): 1 hour

**Total**: ~6-9 hours

## Dependencies

None - all changes are contained within RAGDiff codebase.

## Follow-Up Work

After this implementation:
- Consider adding Config caching with cache keys
- Add metrics for credential resolution performance
- Consider adding credential validation hooks
- Add audit logging for credential usage
