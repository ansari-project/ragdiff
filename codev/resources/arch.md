# RAGDiff Architecture

## Overview

RAGDiff is a flexible framework for comparing Retrieval-Augmented Generation (RAG) systems side-by-side with subjective quality evaluation using LLMs. The architecture follows a clean adapter pattern that enables extensible comparison of multiple RAG tools (Vectara, Goodmem, Agentset) through a unified interface.

The system emphasizes:
- **Adapter Pattern**: Clean separation between comparison logic and tool-specific implementations
- **Subjective Quality Assessment**: LLM-based evaluation (Claude) for qualitative insights
- **Flexible Configuration**: YAML-based configuration with environment variable support and adapter variants
- **Multiple Output Formats**: Display, JSON, JSONL, CSV, and Markdown
- **Batch Processing**: Process multiple queries with comprehensive statistics and holistic summaries
- **SearchVectara Compatibility**: All adapters implement the SearchVectara interface for Ansari Backend integration
- **Multi-Tenant Support**: Thread-safe credential management for SaaS and multi-user environments
- **Thread-Safe Library API**: Production-ready for web services and concurrent usage

## Technology Stack

### Core Dependencies
- **Python**: 3.9.2+ (Modern Python features with broad compatibility)
- **uv**: Fast Python package installer and resolver
- **Typer**: 0.9.0+ (CLI framework with rich terminal output)
- **Rich**: 13.0.0+ (Beautiful terminal formatting and progress tracking)
- **PyYAML**: 6.0+ (Configuration management)
- **python-dotenv**: 1.0.0+ (Environment variable handling)

### RAG Platform Clients
- **anthropic**: 0.25.0+ (Claude API for LLM evaluation)
- **requests**: 2.31.0+ (HTTP client for Vectara API)
- **goodmem-client**: 1.5.5+ (Goodmem RAG platform)
- **agentset**: 0.4.0+ (Agentset RAG-as-a-Service)

### Development Tools
- **pytest**: 7.4.0+ (Testing framework with 230+ tests)
- **pytest-cov**: 4.1.0+ (Test coverage reporting)
- **black**: 23.0.0+ (Code formatting)
- **ruff**: 0.1.0+ (Fast Python linter)
- **mypy**: 1.5.0+ (Static type checking)

### Build System
- **hatchling**: Build backend for packaging
- **MIT License**: Open source licensing

## Directory Structure

```
ragdiff/
├── .claude/                    # Claude Code configuration
│   └── agents/                 # Custom agent definitions
│       └── architecture-documenter.md
├── codev/                      # Development documentation (SPIDER protocol)
│   ├── specs/                  # Feature specifications
│   │   ├── 0001-rag-comparison-harness.md
│   │   ├── 0002-rag-system-generalization.md
│   │   ├── 0003-library-refactoring.md
│   │   └── 0004-multi-tenant-credentials.md
│   ├── plans/                  # Implementation plans
│   │   ├── 0001-rag-comparison-harness.md
│   │   ├── 0003-library-refactoring.md
│   │   └── 0004-multi-tenant-credentials.md
│   ├── reviews/                # Code reviews and evaluations
│   │   ├── 0001-rag-comparison-harness.md
│   │   ├── 0002-adapter-variants.md
│   │   └── 0003-library-refactoring-final-review.md
│   └── resources/              # Architecture documentation
│       └── arch.md            # This file - canonical architecture reference
├── src/                        # Source code (PYTHONPATH=src)
│   ├── __init__.py
│   ├── __main__.py            # Entry point for python -m src
│   └── ragdiff/               # Main package
│       ├── __init__.py        # Public API exports
│       ├── api.py             # Library API functions
│       ├── cli.py             # Typer CLI implementation
│       ├── core/              # Core models and configuration
│       │   ├── __init__.py
│       │   ├── models.py      # Data models (RagResult, ComparisonResult, etc.)
│       │   ├── config.py      # YAML configuration with credential management
│       │   └── errors.py      # Custom exception types
│       ├── adapters/          # RAG tool adapters
│       │   ├── __init__.py
│       │   ├── abc.py         # RagAdapter abstract base class
│       │   ├── base.py        # BaseRagTool (SearchVectara interface)
│       │   ├── factory.py     # Adapter factory with credential support
│       │   ├── registry.py    # Adapter registry with auto-discovery
│       │   ├── vectara.py     # Vectara platform adapter
│       │   ├── goodmem.py     # Goodmem adapter
│       │   ├── agentset.py    # Agentset adapter
│       │   └── search_vectara_mock.py  # Mock SearchVectara for testing
│       ├── comparison/        # Comparison engine
│       │   ├── __init__.py
│       │   └── engine.py      # Parallel/sequential search execution
│       ├── evaluation/        # LLM evaluation
│       │   ├── __init__.py
│       │   └── evaluator.py   # Claude-based quality evaluation
│       └── display/           # Output formatters
│           ├── __init__.py
│           └── formatter.py   # Multiple format support
├── tests/                     # Test suite (230+ tests)
│   ├── test_cli.py
│   ├── test_adapters.py
│   ├── test_api.py           # Library API tests
│   ├── test_multi_tenant.py  # Multi-tenant credential tests
│   ├── test_api_multi_tenant.py  # API multi-tenant integration tests
│   ├── test_thread_safety.py # Thread safety tests
│   ├── test_reentrancy.py    # Reentrancy tests
│   └── ...
├── configs/                   # Configuration files
│   ├── tafsir.yaml           # Tafsir corpus configuration
│   └── mawsuah.yaml          # Mawsuah corpus configuration
├── inputs/                    # Test queries and batch input files
│   └── tafsir-test-queries.txt
├── outputs/                   # Generated results and summaries
│   ├── batch_results_*.jsonl
│   └── holistic_summary_*.md
├── pyproject.toml            # Project metadata and dependencies
├── README.md                 # User documentation
└── .env.example              # Environment variable template
```

## Core Components

### 1. Data Models (`src/ragdiff/core/models.py`)
- **Location**: `src/ragdiff/core/models.py`
- **Purpose**: Define core data structures for RAG results and comparisons
- **Key Classes**:
  - `RagResult`: Normalized search result from any RAG system
    - Fields: `id`, `text`, `score` (0-1 normalized), `source`, `metadata`, `latency_ms`
    - Auto-normalizes scores from different scales (0-1, 0-100, 0-1000)
  - `ComparisonResult`: Complete comparison across multiple tools
    - Fields: `query`, `tool_results` (dict), `errors` (dict), `timestamp`, `llm_evaluation`
    - Methods: `has_errors()`, `get_result_counts()`, `to_dict()`
  - `LLMEvaluation`: LLM-based quality assessment
    - Fields: `llm_model`, `winner`, `analysis`, `quality_scores` (0-100), `metadata`
    - Methods: `to_dict()`
  - `ToolConfig`: Configuration for a RAG tool
    - Fields: `name`, `api_key_env`, `adapter`, `options`, `base_url`, `corpus_id`, `namespace_id_env`, `timeout`, `max_retries`, `default_top_k`, `space_ids`
    - Methods: `validate()`

### 2. Configuration Management (`src/ragdiff/core/config.py`)
- **Location**: `src/ragdiff/core/config.py`
- **Purpose**: Load and validate YAML configuration with environment variable substitution and multi-tenant credential support
- **Key Class**: `Config`
  - **Constructor Parameters**:
    - `config_path`: Optional path to YAML file
    - `config_dict`: Optional configuration dictionary (alternative to file)
    - `credentials`: Optional credential overrides dictionary (env var name -> value)
  - **Credential Resolution**: Implements precedence model for multi-tenant support
  - **Key Methods**:
    - `_get_env_value(env_var_name)`: Resolve credentials with precedence (credentials dict > environment)
    - `_process_env_vars()`: Process `${ENV_VAR}` placeholders using credential resolution
    - `get_tool_config(tool_name)`: Retrieve specific tool configuration
    - `get_llm_config()`: Get LLM evaluation settings
    - `validate()`: Ensure all required credentials are available
  - **Multi-Tenant Features**:
    - Accepts configuration as dictionary (not just files)
    - Thread-safe credential isolation per Config instance
    - No environment variable pollution
    - Supports dynamic configuration from databases

### 3. Abstract Adapter Base (`src/ragdiff/adapters/abc.py`)
- **Location**: `src/ragdiff/adapters/abc.py`
- **Purpose**: Define stable adapter interface with multi-tenant support
- **Key Class**: `RagAdapter(ABC)`
  - **Constructor Parameters**:
    - `config`: ToolConfig object
    - `credentials`: Optional credential overrides dictionary
  - **Credential Management**:
    - `_get_credential(env_var_name)`: Resolve credential with precedence
    - Credentials dict takes precedence over environment variables
  - **Abstract Methods**:
    - `search(query, top_k)`: Execute search and return normalized results
    - `validate_config(config)`: Validate adapter configuration
  - **Optional Methods**:
    - `get_required_env_vars()`: List required environment variables
    - `get_options_schema()`: JSON schema for adapter options
  - **Attributes**:
    - `ADAPTER_API_VERSION`: Version compatibility marker
    - `ADAPTER_NAME`: Unique adapter identifier
    - `config`: Tool configuration
    - `_credentials`: Credential overrides dictionary

### 4. Adapter Factory (`src/ragdiff/adapters/factory.py`)
- **Location**: `src/ragdiff/adapters/factory.py`
- **Purpose**: Registry pattern for creating and managing adapters with credential support
- **Key Function**: `create_adapter(tool_name, config, credentials=None)`
  - Accepts optional credentials dictionary for multi-tenant support
  - Passes credentials to adapter constructor
  - Supports adapter variants via `config.adapter` field
  - Enables multiple configurations of same adapter
- **Registry Management**:
  - Auto-imports adapter modules to trigger registration
  - `get_available_adapters()`: List registered adapter names
  - Maintains backward compatibility while adding credential support

### 5. Public API (`src/ragdiff/api.py`)
- **Location**: `src/ragdiff/api.py`
- **Purpose**: Provide programmatic interface for library usage
- **Multi-Tenant Functions**:
  - `load_config(config, credentials=None)`: Load configuration with credential overrides
    - Accepts file path, Path object, or dictionary
    - Returns Config object with encapsulated credentials
  - `query(config, query_text, tool, top_k=5)`: Single query execution
    - Accepts Config object (new) or file path (backward compatible)
    - Uses credentials from Config object
  - `compare(config, query_text, tools=None, top_k=5, parallel=True, evaluate=False)`: Multi-tool comparison
    - Accepts Config object or file path
    - Thread-safe for concurrent requests
  - `run_batch(config, queries, tools=None, top_k=5, parallel=True, evaluate=False)`: Batch processing
    - Accepts Config object or file path
    - Maintains credential isolation across queries
- **Helper Functions**:
  - `validate_config(config_path)`: Validate configuration file
  - `get_available_adapters()`: List available adapter metadata
  - `evaluate_with_llm(result, model, api_key)`: LLM evaluation

### 6. Tool Adapters (Multi-Tenant Enhanced)

All adapters now support multi-tenant credentials through the base class:

#### Vectara Adapter (`src/ragdiff/adapters/vectara.py`)
- **Constructor**: `__init__(config, credentials=None)`
- **Credential Resolution**: Uses `self._get_credential(config.api_key_env)`
- **Thread Safety**: No shared state, credentials isolated per instance

#### Goodmem Adapter (`src/ragdiff/adapters/goodmem.py`)
- **Constructor**: `__init__(config, credentials=None)`
- **Credential Resolution**: Uses base class `_get_credential()` method
- **Multiple Space Support**: Configurable space_ids per tenant

#### Agentset Adapter (`src/ragdiff/adapters/agentset.py`)
- **Constructor**: `__init__(config, credentials=None)`
- **Dual Credentials**: Handles both API token and namespace ID
- **Credential Resolution**: Resolves both credentials independently

### 7. Comparison Engine (`src/ragdiff/comparison/engine.py`)
- **Location**: `src/ragdiff/comparison/engine.py`
- **Purpose**: Orchestrate parallel or sequential RAG tool searches
- **Key Class**: `ComparisonEngine`
  - Thread-safe execution with ThreadPoolExecutor
  - No shared mutable state between searches
  - Each adapter instance has isolated credentials
  - Methods remain unchanged but benefit from thread-safe adapters

### 8. LLM Evaluator (`src/ragdiff/evaluation/evaluator.py`)
- **Location**: `src/ragdiff/evaluation/evaluator.py`
- **Purpose**: Use Claude to provide qualitative RAG result evaluation
- **Multi-Tenant Support**:
  - API key can be passed per evaluation
  - Config object provides credential resolution for LLM API key
  - Thread-safe for concurrent evaluations

### 9. CLI (`src/ragdiff/cli.py`)
- **Location**: `src/ragdiff/cli.py`
- **Purpose**: Typer-based command-line interface
- **Multi-Tenant Compatibility**:
  - CLI uses library API functions internally
  - Environment variables used by default (single-tenant mode)
  - Could be extended to accept credentials file for multi-tenant CLI usage

## Multi-Tenant Credential Architecture

### Credential Resolution Model

The system implements a clear precedence model for credential resolution:

```
Priority Order (Highest to Lowest):
1. Passed credentials dict (via Config constructor)
2. Process environment variables (os.environ)
3. .env file (via python-dotenv)
4. None (causes validation error)
```

### Thread Safety Guarantees

1. **No Global State**: All credentials stored in instance variables
2. **Immutable Config**: Config objects are read-only after creation
3. **Isolated Adapters**: Each adapter instance has its own credentials
4. **No Environment Pollution**: Passed credentials never modify os.environ
5. **Concurrent Safety**: Multiple requests can use different credentials simultaneously

### Multi-Tenant Usage Patterns

#### Pattern 1: Web Service (FastAPI)
```python
from ragdiff import load_config, query

@app.post("/api/search")
async def search(request: SearchRequest, tenant_id: str):
    # Get tenant-specific credentials from database
    tenant_creds = get_tenant_credentials(tenant_id)

    # Create config with tenant credentials
    config = load_config("config.yaml", credentials=tenant_creds)

    # Execute query with isolated credentials
    results = query(config, request.query, tool="vectara")
    return {"results": [r.to_dict() for r in results]}
```

#### Pattern 2: Dynamic Configuration
```python
# Build config from database
config_dict = {
    "tools": {
        "vectara": {
            "api_key_env": "VECTARA_API_KEY",
            "corpus_id": tenant.corpus_id
        }
    }
}

# Load with tenant credentials
config = load_config(
    config_dict,  # Dict instead of file
    credentials={"VECTARA_API_KEY": tenant.api_key}
)

results = query(config, "query", tool="vectara")
```

#### Pattern 3: Temporary Credentials
```python
# Use short-lived credentials from OAuth/STS
temp_creds = get_temporary_credentials()

config = load_config(
    "config.yaml",
    credentials={
        "VECTARA_API_KEY": temp_creds.access_token,
        "ANTHROPIC_API_KEY": temp_creds.llm_token
    }
)

# Credentials expire with the Config object
result = compare(config, "query", evaluate=True)
```

### Security Considerations

1. **Credential Isolation**: Each Config object has isolated credentials
2. **No Leakage**: Credentials from one request never affect another
3. **No Persistence**: Credentials exist only in memory during request
4. **Validation**: All credentials validated at Config creation time
5. **Error Messages**: Careful not to expose credential values in errors

### Backward Compatibility

The multi-tenant implementation maintains full backward compatibility:

1. **File Paths Still Work**: `query("config.yaml", "query", tool="vectara")`
2. **Environment Variables**: Default behavior uses environment variables
3. **No Breaking Changes**: Existing code continues to work unchanged
4. **Opt-In Enhancement**: Multi-tenant features only activate when credentials passed

## Data Flow

### Single Query Comparison Flow (Multi-Tenant Enhanced)
```
1. User Input (API/CLI)
   └─> query/compare with optional credentials

2. Configuration Loading
   └─> Config created with credentials dict
   └─> Credentials encapsulated in Config object
   └─> ${ENV_VAR} resolved using credential precedence

3. Adapter Creation
   └─> Factory passes credentials to adapter
   └─> Each adapter has isolated credentials
   └─> Validates credentials at creation time

4. Comparison Execution
   └─> ComparisonEngine.run_comparison()
   └─> Parallel/Sequential execution (thread-safe)
   └─> Each adapter uses its own credentials
   └─> No credential sharing between adapters

5. Optional LLM Evaluation
   └─> LLMEvaluator uses Config's credential resolution
   └─> API key from credentials dict or environment
   └─> Thread-safe evaluation

6. Output Formatting
   └─> ComparisonFormatter (unchanged)
   └─> No credential exposure in output

7. Response to User
   └─> Results contain no credential information
   └─> Credentials garbage collected with Config
```

### Multi-Tenant Request Flow
```
1. Tenant Request Arrives
   └─> Extract tenant ID from auth/headers

2. Retrieve Tenant Credentials
   └─> Database lookup for tenant settings
   └─> Get API keys, corpus IDs, etc.

3. Create Tenant Config
   └─> load_config() with tenant credentials
   └─> Config object encapsulates all settings

4. Execute Operations
   └─> Pass Config to query/compare/run_batch
   └─> All operations use tenant's credentials
   └─> Concurrent requests have isolated configs

5. Cleanup
   └─> Config garbage collected after request
   └─> No credential residue in memory
   └─> No environment variable changes
```

## Key Design Decisions

### 1. Config Object Pattern for Credentials
**Decision**: Pass credentials at Config creation, then pass Config to API functions.

**Rationale**:
- Clear separation between config loading and execution
- Config validation happens once at creation
- Credentials encapsulated and protected
- Easier to test and reason about
- Natural fit for dependency injection patterns

**Alternative Considered**: Pass credentials to each API function
- Rejected: Would require credentials in every call
- Rejected: Harder to validate consistently
- Rejected: More complex API signatures

### 2. Credential Dictionary Format
**Decision**: Use environment variable names as keys (e.g., `{"VECTARA_API_KEY": "value"}`).

**Rationale**:
- Consistent with existing configuration
- No new mapping layer needed
- Clear what each credential is for
- Works with ${ENV_VAR} substitution

**Alternative Considered**: Use adapter field names
- Rejected: Would require mapping logic
- Rejected: Less clear connection to environment

### 3. Precedence Model
**Decision**: Passed credentials override environment variables.

**Rationale**:
- Explicit values should override implicit ones
- Enables multi-tenant without environment changes
- Predictable and easy to understand
- Standard practice in configuration systems

### 4. Thread Safety via Immutability
**Decision**: Make Config and credentials immutable after creation.

**Rationale**:
- Eliminates race conditions
- No locks needed
- Safe to share Config between threads (read-only)
- Simple mental model

### 5. Backward Compatibility First
**Decision**: Accept both Config objects and file paths in API functions.

**Rationale**:
- No breaking changes for existing users
- Gradual migration path
- Can ship immediately without deprecation period
- Reduces friction for adoption

## Integration Points

### External Services (Multi-Tenant Ready)

All external service integrations now support per-request credentials:

#### Vectara Platform
- Credentials passed via Config object
- Each request can use different API key
- Corpus ID configurable per tenant

#### Goodmem
- API key from credentials dict or environment
- Space IDs configurable per tenant
- Fallback mechanisms unchanged

#### Agentset
- Both token and namespace ID support credentials
- Per-tenant namespace isolation
- Rerank options configurable

#### Anthropic Claude
- LLM API key from Config credential resolution
- Per-tenant model selection possible
- Isolated evaluation contexts

## Development Patterns

### 1. Adding a New Multi-Tenant Ready Adapter

```python
from typing import Optional
from .abc import RagAdapter
from ..core.models import RagResult, ToolConfig

class MyToolAdapter(RagAdapter):
    ADAPTER_NAME = "mytool"
    ADAPTER_API_VERSION = "1.0.0"

    def __init__(
        self,
        config: ToolConfig,
        credentials: Optional[dict[str, str]] = None
    ):
        super().__init__(config, credentials)

        # Use credential resolution
        api_key = self._get_credential(config.api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"Missing API key: {config.api_key_env}"
            )

        self.api_key = api_key
        # Initialize tool-specific client

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        # Implementation using self.api_key
        pass
```

### 2. Multi-Tenant Web Service Pattern

```python
from fastapi import FastAPI, Depends
from ragdiff import load_config, compare

app = FastAPI()

async def get_tenant_config(tenant_id: str = Depends(get_tenant_id)):
    """Load tenant-specific configuration."""
    tenant = await db.get_tenant(tenant_id)

    config = load_config(
        "base_config.yaml",
        credentials={
            "VECTARA_API_KEY": tenant.vectara_key,
            "GOODMEM_API_KEY": tenant.goodmem_key,
            "ANTHROPIC_API_KEY": tenant.llm_key
        }
    )
    return config

@app.post("/api/compare")
async def compare_endpoint(
    request: CompareRequest,
    config: Config = Depends(get_tenant_config)
):
    """Multi-tenant comparison endpoint."""
    result = compare(
        config,
        request.query,
        tools=request.tools,
        evaluate=request.evaluate
    )
    return result.to_dict()
```

### 3. Testing Multi-Tenant Functionality

```python
def test_multi_tenant_isolation():
    """Test credential isolation between tenants."""
    # Create configs for different tenants
    config_a = load_config(
        {"tools": {"vectara": {...}}},
        credentials={"VECTARA_API_KEY": "tenant_a_key"}
    )

    config_b = load_config(
        {"tools": {"vectara": {...}}},
        credentials={"VECTARA_API_KEY": "tenant_b_key"}
    )

    # Verify isolation
    assert config_a._credentials != config_b._credentials

    # Run concurrent queries
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(query, config_a, "query", "vectara")
        future_b = executor.submit(query, config_b, "query", "vectara")

        results_a = future_a.result()
        results_b = future_b.result()

    # Verify both completed successfully with own credentials
    assert results_a and results_b
```

## Performance Considerations

### Multi-Tenant Performance

- **Credential Resolution**: O(1) dictionary lookup, negligible overhead
- **Config Creation**: One-time cost per request, not per query
- **Memory**: Each Config holds only credential references, minimal overhead
- **Thread Safety**: No locks needed due to immutability
- **Garbage Collection**: Configs cleaned up automatically after request

### Optimization Strategies

- **Config Reuse**: Same tenant can reuse Config across multiple queries
- **Connection Pooling**: Adapters can implement per-tenant connection pools
- **Credential Caching**: Application layer can cache validated credentials
- **Batch Operations**: Multi-tenant batch processing works efficiently

## Testing Coverage

### Multi-Tenant Test Files

- **`tests/test_multi_tenant.py`**: Config credential tests (15 tests)
  - Credential dictionary acceptance
  - Precedence validation
  - Environment variable substitution
  - Validation with missing credentials
  - Config path/dict mutual exclusion

- **`tests/test_api_multi_tenant.py`**: API integration tests (12 tests)
  - Config object acceptance
  - Backward compatibility
  - Multi-tenant isolation
  - Concurrent request handling

- **`tests/test_thread_safety.py`**: Thread safety tests (8 tests)
  - Concurrent config creation
  - Parallel query execution
  - Adapter thread safety
  - No credential leakage

- **`tests/test_reentrancy.py`**: Reentrancy tests (5 tests)
  - Recursive adapter calls
  - Nested configurations
  - State isolation verification

## Security Implications

### Credential Security

1. **No Logging**: Credentials never logged, even at debug level
2. **No Serialization**: Credentials excluded from to_dict() methods
3. **Memory Only**: Credentials never written to disk
4. **Scoped Lifetime**: Credentials garbage collected with Config
5. **Error Sanitization**: Error messages don't expose credential values

### Multi-Tenant Security

1. **Tenant Isolation**: Complete credential isolation between tenants
2. **No Cross-Contamination**: One tenant cannot access another's credentials
3. **Audit Trail**: Application layer can log credential usage per tenant
4. **Rate Limiting**: Can be implemented per tenant at application layer
5. **Credential Rotation**: Supports dynamic credential updates without restart

## Future Architecture Considerations

### Planned Enhancements

1. **Credential Providers**: Pluggable credential sources (AWS Secrets, Vault)
2. **Credential Refresh**: Automatic refresh for expiring credentials
3. **Audit Logging**: Built-in credential usage audit trail
4. **Performance Metrics**: Per-tenant usage and performance tracking
5. **Circuit Breakers**: Per-tenant circuit breakers for failed requests

### Potential Extensions

1. **Config Caching**: Cache validated configs with TTL
2. **Lazy Credential Loading**: Load credentials only when needed
3. **Credential Validation Hooks**: Custom validation per adapter
4. **Multi-Region Support**: Region-specific credentials
5. **OAuth/OIDC Integration**: Direct OAuth token support

---

**Document Status**: Updated with Multi-Tenant Credential Support
**Project Version**: 0.1.0 (with multi-tenant features)
**Last Updated**: 2025-10-21 - Added comprehensive multi-tenant architecture
**Architecture Changes**:
- Added Config object pattern with credentials dictionary
- Enhanced all adapters with credential resolution
- Updated API functions to accept Config objects
- Maintained full backward compatibility
**Next Review**: After credential provider implementation or security audit
