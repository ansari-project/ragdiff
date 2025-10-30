# RAGDiff v2.1 Architecture

## Overview

RAGDiff v2.1 is a domain-centric experimentation framework for comparing Retrieval-Augmented Generation (RAG) systems. The architecture follows a domain-first organizational model that treats experiments as first-class objects with full reproducibility and structured comparison capabilities.

Key architectural principles:
- **Domain-Driven Design**: Experiments organized by knowledge domains (tafsir, legal, medical)
- **Providers = Tool + Configuration**: Enable A/B testing of different configurations
- **Immutable Runs**: Timestamped, versioned, and fully reproducible experimental results
- **File-System-First**: All configuration in YAML, all results in JSON
- **LLM-Based Evaluation**: Structured comparison using multiple LLM providers via LiteLLM with parallel execution
- **Clean Separation**: Core models, providers interface, execution engine, and CLI are clearly separated

## Technology Stack

### Core Framework
- **Python**: 3.9.2+ (Type hints, modern async support)
- **Pydantic**: 2.0+ (Data validation and serialization)
- **Typer**: 0.9.0+ (CLI framework)
- **Rich**: 13.0.0+ (Beautiful terminal UI with progress bars)
- **PyYAML**: 6.0+ (Configuration management)
- **python-dotenv**: 1.0.0+ (Environment variable handling)

### LLM Integration
- **LiteLLM**: 1.0+ (Multi-provider LLM support)
  - Supports: OpenAI GPT, Anthropic Claude, Google Gemini, Azure OpenAI
  - Cost tracking and retry logic built-in
  - Unified interface across providers
  - Parallel evaluation support with ThreadPoolExecutor

### RAG System Clients
- **requests**: 2.31.0+ (HTTP client for Vectara and OpenAPI providers)
- **agentset**: 0.4.0+ (Agentset RAG platform)
- **pymongo**: 4.0.0+ (MongoDB Atlas Vector Search)
- **openai**: 1.0.0+ (Embeddings for MongoDB)
- **jmespath**: 1.0.1+ (JSON query language for OpenAPI response mapping)
- **rank_bm25**: BM25 text ranking
- **faiss-cpu**: FAISS vector search
- **sentence-transformers**: Text embeddings for FAISS/BM25

### Development Tools
- **pytest**: 7.4.0+ (Testing framework - comprehensive test suite)
- **pytest-cov**: 4.1.0+ (Coverage reporting)
- **ruff**: 0.1.0+ (Fast Python linter and formatter)
- **pre-commit**: 3.0.0+ (Git hooks for code quality)
- **responses**: 0.24.0+ (HTTP mocking for tests)

## Directory Structure

```
ragdiff/
├── src/ragdiff/                    # Main package (v2.0+ architecture)
│   ├── __init__.py                 # Public API exports
│   ├── __main__.py                 # Entry point for python -m ragdiff
│   ├── cli.py                      # CLI implementation (run, compare, init, generate-provider)
│   ├── version.py                  # Version information (v2.1.2)
│   │
│   ├── core/                       # Core data models and utilities
│   │   ├── __init__.py
│   │   ├── models.py               # Pydantic models (Domain, Run, Comparison, etc.)
│   │   ├── loaders.py              # YAML and text file loading
│   │   ├── storage.py              # JSON persistence utilities
│   │   ├── env_vars.py             # Environment variable handling
│   │   ├── paths.py                # Path utilities
│   │   ├── errors.py               # Custom exceptions
│   │   ├── logging.py              # Logging configuration
│   │   └── serialization.py        # JSON serialization helpers
│   │
│   ├── providers/                  # RAG provider implementations
│   │   ├── __init__.py             # Auto-imports for registration
│   │   ├── abc.py                  # Provider abstract base class
│   │   ├── registry.py             # Singleton provider registry
│   │   ├── factory.py              # Provider factory with validation
│   │   ├── vectara.py              # Vectara provider implementation
│   │   ├── mongodb.py              # MongoDB Atlas provider
│   │   ├── agentset.py             # Agentset provider
│   │   ├── goodmem.py              # Goodmem provider
│   │   ├── faiss.py                # FAISS vector search provider
│   │   ├── bm25.py                 # BM25 text search provider
│   │   ├── openapi.py              # Generic OpenAPI provider
│   │   └── openapi_utils.py        # OpenAPI utilities (JMESPath mapping)
│   │
│   ├── execution/                  # Query execution engine
│   │   ├── __init__.py
│   │   └── executor.py             # RunExecutor with parallel execution
│   │
│   ├── comparison/                 # LLM-based comparison
│   │   ├── __init__.py
│   │   ├── evaluator.py            # ComparisonEvaluator with parallel evaluation
│   │   └── reference_evaluator.py  # Reference-based evaluation
│   │
│   ├── display/                    # Output formatting
│   │   ├── __init__.py
│   │   └── formatting.py           # Table, JSON, Markdown formatters
│   │
│   └── openapi/                    # OpenAPI specification tools
│       ├── __init__.py
│       ├── models.py               # Data models (EndpointInfo, AuthScheme)
│       ├── parser.py               # OpenAPI 3.x spec parser
│       ├── ai_analyzer.py          # AI-powered analysis
│       └── generator.py            # Configuration generator
│
├── tests/                          # Test suite
│   ├── test_core.py                # Core models tests
│   ├── test_providers.py           # Provider implementations tests
│   ├── test_execution.py           # Execution engine tests
│   ├── test_comparison.py          # Comparison tests
│   ├── test_cli.py                 # CLI tests
│   ├── test_squad_demo.py          # SQuAD demo tests
│   └── parity/                     # Parity testing framework
│       ├── __init__.py
│       └── framework.py
│
├── domains/                        # Domain experiment directories
│   └── <domain-name>/              # e.g., tafsir, legal, medical
│       ├── domain.yaml             # Domain configuration
│       ├── providers/              # Provider configurations
│       │   └── <provider-name>.yaml  # e.g., vectara-mmr.yaml
│       ├── query-sets/             # Query collections
│       │   ├── <name>.txt         # Plain text queries
│       │   └── <name>.jsonl       # Queries with references
│       ├── runs/                   # Execution results
│       │   └── YYYY-MM-DD/        # Date-organized runs
│       │       └── <run-id>.json  # Run results
│       └── comparisons/            # Comparison results
│           └── YYYY-MM-DD/        # Date-organized comparisons
│               └── <comparison-id>.json
│
├── examples/                       # Example usage
│   ├── squad-demo/                # SQuAD dataset demo
│   │   ├── squad_demo_api.ipynb   # Jupyter notebook demo
│   │   └── ...                    # Demo data and configs
│   └── comparison-reports/        # Example comparison outputs
│
├── codev/                          # Development artifacts (SPIDER protocol)
│   ├── specs/                     # Feature specifications (TICK protocol)
│   ├── plans/                     # Implementation plans
│   ├── reviews/                   # Code reviews
│   └── resources/                 # Architecture and design docs
│       └── arch.md                # This document
│
├── pyproject.toml                  # Package configuration
├── README.md                       # User documentation
└── CLAUDE.md                       # Development instructions
```

## Core Components

### 1. Data Models (`src/ragdiff/core/models.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/core/models.py`
**Purpose**: Define v2.0+ data structures using Pydantic for validation and serialization

#### Key Classes

**Domain**:
- Represents a knowledge area (e.g., tafsir, legal, medical)
- Fields: `name`, `description`, `variables`, `secrets`, `evaluator`, `metadata`
- Scopes all experiments within a problem space
- Loaded from `domains/<domain>/domain.yaml`

**ProviderConfig**:
- Configuration for a RAG provider (tool + settings)
- Fields: `name`, `tool`, `config`, `metadata`
- Enables multiple configurations of same tool
- Loaded from `domains/<domain>/providers/<name>.yaml`
- **Note**: Called "ProviderConfig" (not "SystemConfig") in v2.1+

**Query**:
- Individual query with optional reference answer
- Fields: `text`, `reference`, `metadata`
- Supports both plain text and JSONL formats

**QuerySet**:
- Collection of queries (max 1000)
- Fields: `name`, `domain`, `queries`
- Types: `query_only` (.txt) or `query_reference` (.jsonl)
- Loaded from `domains/<domain>/query-sets/<name>.[txt|jsonl]`

**RetrievedChunk**:
- Single retrieved text chunk from a RAG provider
- Fields: `content`, `score`, `metadata` (source_id, doc_id, chunk_id)
- Normalized output format across all providers

**QueryResult**:
- Result for a single query execution
- Fields: `query`, `retrieved`, `reference`, `duration_ms`, `error`
- Captures both successful results and failures

**Run**:
- Complete execution: QuerySet × Provider
- Fields: `id`, `label`, `domain`, `provider`, `query_set`, `status`, `results`, `provider_config`, `query_set_snapshot`, `started_at`, `completed_at`, `metadata`
- Statuses: `pending`, `running`, `completed`, `failed`, `partial`
- Stores complete snapshots for reproducibility
- Saved to `domains/<domain>/runs/YYYY-MM-DD/<run-id>.json`

**Comparison**:
- Multi-run comparison with LLM evaluation
- Fields: `id`, `label`, `domain`, `runs`, `evaluations`, `timestamp`, `evaluator_config`, `metadata`
- Contains per-query evaluations with winner determination
- Saved to `domains/<domain>/comparisons/YYYY-MM-DD/<comparison-id>.json`

**EvaluationResult**:
- Individual query evaluation result
- Fields: `query`, `reference`, `run_results`, `evaluation`
- Structured output from LLM comparison

### 2. File Loaders (`src/ragdiff/core/loaders.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/core/loaders.py`
**Purpose**: Load configuration and query files from disk

**Key Functions**:

`load_domain(domain: str, domains_dir: Path) -> Domain`:
- Loads domain.yaml configuration
- Preserves ${VAR_NAME} placeholders for security
- Validates domain structure

`load_provider_config(domain: str, provider_name: str, domains_dir: Path) -> ProviderConfig`:
- Loads provider YAML configuration
- Validates tool references
- Preserves environment variables

`load_query_set(domain: str, query_set_name: str, domains_dir: Path) -> QuerySet`:
- Auto-detects format (.txt or .jsonl)
- Parses queries with optional references
- Enforces 1000 query limit

`load_queries_from_text(file_path: Path) -> list[Query]`:
- Parses plain text queries (one per line)
- Creates Query objects with no reference

`load_queries_from_jsonl(file_path: Path) -> list[Query]`:
- Parses JSONL format with query/reference pairs
- Validates JSON structure

### 3. Storage Utilities (`src/ragdiff/core/storage.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/core/storage.py`
**Purpose**: Persist runs and comparisons to JSON

**Key Functions**:

`save_run(run: Run, domains_dir: Path) -> Path`:
- Saves run to date-organized directory
- Creates `runs/YYYY-MM-DD/<run-id>.json`
- Returns saved file path

`load_run(domain: str, run_id: str | UUID, domains_dir: Path) -> Run`:
- Loads run from JSON file (supports short prefixes)
- Validates and reconstructs Run object

`save_comparison(comparison: Comparison, domains_dir: Path) -> Path`:
- Saves comparison results
- Creates `comparisons/YYYY-MM-DD/<comparison-id>.json`

`load_comparison(domain: str, comparison_id: str | UUID, domains_dir: Path) -> Comparison`:
- Loads comparison from JSON
- Reconstructs Comparison object

`generate_run_label(domain: str, provider: str, date_str: str, domains_dir: Path) -> str`:
- Auto-generates unique run labels (e.g., "vectara-20251030-001")

`generate_comparison_label(domain: str, date_str: str, domains_dir: Path) -> str`:
- Auto-generates unique comparison labels (e.g., "comparison-20251030-001")

### 4. Provider Interface (`src/ragdiff/providers/`)

#### Abstract Base Class (`abc.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/providers/abc.py`
**Purpose**: Define common interface for all RAG providers

```python
class Provider(ABC):
    """Abstract base class for RAG providers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize with configuration dictionary."""
        self.config = config

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search and return ranked chunks."""
        pass
```

#### Tool Registry (`registry.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/providers/registry.py`
**Purpose**: Singleton registry for provider registration

**Key Components**:

`ToolRegistry` (Singleton):
- `_instance`: Single registry instance
- `_tools`: Dictionary of registered tools
- Thread-safe singleton pattern

`register_tool(name: str, tool_class: type[Provider])`:
- Registers provider class with name
- Called at module import time
- Validates provider implements Provider interface

`get_tool(name: str) -> type[Provider]`:
- Retrieves registered provider class
- Raises error if not found

`list_tools() -> list[str]`:
- Returns all registered provider names

#### Provider Factory (`factory.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/providers/factory.py`
**Purpose**: Create provider instances from configuration

`create_provider(config: ProviderConfig) -> Provider`:
- Gets provider class from registry
- Instantiates with configuration
- Handles environment variable substitution
- Returns configured Provider instance

#### Provider Implementations

**Vectara Provider** (`vectara.py`):
- HTTP-based API client
- Supports MMR and Slingshot reranking
- Corpus ID configuration
- Score normalization (0-1 range)

**MongoDB Provider** (`mongodb.py`):
- Atlas Vector Search integration
- Dynamic query embedding via OpenAI
- Configurable field mappings
- Metadata extraction

**Agentset Provider** (`agentset.py`):
- Namespace-based retrieval
- Optional reranking
- Multi-space support
- Fallback handling

**Goodmem Provider** (`goodmem.py`):
- Goodmem RAG platform integration
- Namespace-based search
- API key authentication

**FAISS Provider** (`faiss.py`):
- Local vector search using FAISS
- Sentence transformer embeddings
- In-memory or file-based indices
- Configurable distance metrics

**BM25 Provider** (`bm25.py`):
- Text-based ranking using BM25 algorithm
- No embeddings required
- Configurable parameters (k1, b)
- Lightweight and fast

**OpenAPI Provider** (`openapi.py`):
- Generic adapter for any REST API
- Configuration-driven (zero code needed)
- JMESPath response mapping (via `openapi_utils.py`)
- Bearer, API Key, and Basic authentication
- Template variable substitution (${query}, ${top_k})
- AI-powered config generation from OpenAPI specs

### 5. Execution Engine (`src/ragdiff/execution/executor.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/execution/executor.py`
**Purpose**: Execute query sets against providers with parallel processing

**Key Function**: `execute_run()`

**Main Flow**:
- Loads domain, provider config, and query set
- Creates pending Run object
- Uses ThreadPoolExecutor for parallel queries
- Captures per-query timing and errors
- Updates Run status based on results
- Preserves provider config and query set snapshots
- Saves run to disk

**Error Handling**:
- Per-query error isolation
- Partial success support (some queries fail)
- Comprehensive error messages with stack traces

**Progress Tracking**:
- Callback interface: `callback(current: int, total: int, query: str)`
- Real-time progress updates for UI

### 6. Comparison Engine (`src/ragdiff/comparison/evaluator.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/comparison/evaluator.py`
**Purpose**: Compare runs using LLM evaluation via LiteLLM with parallel execution

**Key Function**: `compare_runs()`

**Constructor Parameters**:
- `domain`: Domain name
- `run_ids`: List of run IDs to compare
- `label`: Optional human-readable label
- `model`: LLM model override (default: use domain evaluator)
- `temperature`: Temperature override
- `max_retries`: Retry count for LLM failures (default: 3)
- `concurrency`: Max concurrent evaluations (default: 1 for sequential)
- `progress_callback`: Optional callback for progress updates
- `domains_dir`: Root domains directory

**Main Flow**:
- Loads domain and all runs
- Validates runs are from same domain and query set
- Gets evaluator config (with overrides if provided)
- Validates API key is available
- Evaluates queries (parallel or sequential based on concurrency)
- Creates Comparison object with results
- Saves comparison to disk

**Parallel Evaluation** (Spec 0007):
- Uses ThreadPoolExecutor when `concurrency > 1`
- Maintains query order using index-based storage
- Per-query error isolation (failures don't crash comparison)
- Real-time progress tracking via callback
- Significantly faster for large query sets (10x+ speedup)

**LLM Integration**:
- Uses LiteLLM for multi-provider support
- Structured prompts for consistent evaluation
- Retry logic with exponential backoff
- Cost tracking via `litellm.completion_cost()`
- Parses both JSON and text responses
- Normalizes provider-specific keys to generic a/b format

**Evaluation Process**:
1. Format retrieved chunks for each provider
2. Build evaluation prompt with query and results
3. Call LLM for winner determination
4. Parse structured response
5. Calculate quality scores
6. Track costs and metadata

### 7. CLI Interface (`src/ragdiff/cli.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/cli.py`
**Purpose**: Command-line interface for all operations

#### Commands

**`init` Command**:
```bash
ragdiff init <domain-name>
```
- Creates new domain structure
- Generates template domain.yaml
- Creates directories for providers, query-sets, runs, comparisons

**`run` Command**:
```bash
ragdiff run <domain> <provider> <query-set> [OPTIONS]
```
- Executes query set against provider
- Shows Rich progress bar during execution
- Saves run to `domains/<domain>/runs/YYYY-MM-DD/`
- Displays results in chosen format

**Options**:
- `--domains-dir`: Custom domains directory
- `--concurrency`: Parallel execution threads (default: 10)
- `--timeout`: Query timeout in seconds
- `--format`: Output format (table, json, markdown)
- `--output`: Save output to file
- `--quiet`: Suppress progress output

**`compare` Command**:
```bash
ragdiff compare <domain> <run-id-1> <run-id-2> [...] [OPTIONS]
```
- Loads specified runs by ID (supports short prefixes)
- Performs LLM evaluation (parallel or sequential)
- Saves comparison results
- Displays winner analysis

**Options**:
- `--domains-dir`: Custom domains directory
- `--model`: Override LLM model
- `--temperature`: Override temperature
- `--concurrency`: Max concurrent evaluations (default: 5)
- `--format`: Output format (table, json, markdown)
- `--output`: Save output to file
- `--quiet`: Suppress progress output

**`generate-provider` Command**:
```bash
ragdiff generate-provider <openapi-spec-url-or-path> [OPTIONS]
```
- Parses OpenAPI 3.x specification
- Uses AI to analyze endpoints and generate config
- Creates provider YAML configuration
- Interactive mode with user approval

**Options**:
- `--output`: Output file path
- `--model`: LLM model for analysis (default: gpt-4o)

**Output Formats**:
- `table`: Rich terminal tables with colors (default)
- `json`: Structured JSON output
- `markdown`: Markdown tables for documentation

### 8. Display Formatting (`src/ragdiff/display/formatting.py`)

**Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/display/formatting.py`
**Purpose**: Format output for different display modes

**Key Functions**:

`format_run_results(run: Run, format: str) -> str`:
- Formats run results for display
- Supports table, JSON, markdown formats

`format_comparison_results(comparison: Comparison, format: str) -> str`:
- Formats comparison for display
- Shows winner determination and scores

## Utility Functions & Helpers

### Environment Variable Resolution (`src/ragdiff/core/env_vars.py`)

`resolve_env_var(value: str) -> str`:
- Replaces ${VAR_NAME} with environment value
- Raises error if variable not found
- Used throughout for credential management

`resolve_env_vars_recursive(obj: Any) -> Any`:
- Recursively resolves variables in nested structures
- Handles dicts, lists, and strings
- Preserves non-string values

### Path Utilities (`src/ragdiff/core/paths.py`)

`get_domain_path(domain: str, domains_dir: Path) -> Path`:
- Returns path to domain directory
- Creates directory if needed

`get_runs_dir(domain: str, domains_dir: Path) -> Path`:
- Returns path to runs directory
- Creates date-organized subdirectories

`get_providers_dir(domain: str, domains_dir: Path) -> Path`:
- Returns path to providers configuration directory

`get_query_sets_dir(domain: str, domains_dir: Path) -> Path`:
- Returns path to query sets directory

`get_comparisons_dir(domain: str, domains_dir: Path) -> Path`:
- Returns path to comparisons directory

### Logging Configuration (`src/ragdiff/core/logging.py`)

`setup_logging(level: str = "INFO")`:
- Configures structured logging
- Sets up formatters and handlers
- Used for debugging and monitoring

`get_logger(name: str)`:
- Returns configured logger instance

## Data Flow

### Query Execution Flow (v2.0+)

```
1. User invokes CLI
   └─> ragdiff run tafsir vectara-mmr basic

2. Load Domain Configuration
   └─> load_domain("domains/tafsir/domain.yaml")
   └─> Domain object with variables and evaluator config

3. Load Provider Configuration
   └─> load_provider_config("tafsir", "vectara-mmr", domains_dir)
   └─> ProviderConfig with tool="vectara" and settings

4. Create Provider Instance
   └─> create_provider(provider_config)
   └─> Registry lookup for "vectara" provider class
   └─> VectaraProvider instance with resolved env vars

5. Load Query Set
   └─> load_query_set("tafsir", "basic", domains_dir)
   └─> QuerySet with list of Query objects

6. Execute Queries
   └─> execute_run(domain, provider, query_set)
   └─> ThreadPoolExecutor for parallel execution
   └─> Progress callbacks to CLI for Rich progress bar
   └─> Capture results and timing per query

7. Save Run
   └─> save_run(run, domains_dir)
   └─> Creates "runs/YYYY-MM-DD/<run-id>.json"
   └─> Includes config snapshots for reproducibility

8. Display Results
   └─> format_run_results(run, format="table")
   └─> Rich terminal table with results
```

### Comparison Flow (v2.0+)

```
1. User invokes comparison
   └─> ragdiff compare tafsir run1 run2 run3 --concurrency 10

2. Load Domain
   └─> load_domain("tafsir", domains_dir)
   └─> Get evaluator configuration

3. Load Runs
   └─> Find and load each run by ID (supports short prefixes)
   └─> Validate all runs are from same domain
   └─> Check query alignment

4. Create Evaluator Config
   └─> Use domain evaluator config or apply overrides
   └─> Validate API key is available for model

5. Evaluate Each Query (Parallel)
   └─> ThreadPoolExecutor with max_workers=concurrency
   └─> For each query across runs:
       └─> Gather results from all providers
       └─> Format evaluation prompt
       └─> Submit to thread pool
   └─> Process completed evaluations:
       └─> Call LLM for analysis
       └─> Parse winner and scores
       └─> Handle retries on failure
       └─> Update progress callback

6. Save Comparison
   └─> save_comparison(comparison, domains_dir)
   └─> Creates "comparisons/YYYY-MM-DD/<comparison-id>.json"

7. Display Results
   └─> format_comparison_results(comparison, format="table")
   └─> Show winner statistics and analysis
```

## API Structure

### v2.0+ CLI Commands

The v2.0+ CLI provides four main commands:

#### `ragdiff init`
Initialize a new domain with directory structure.

**Parameters**:
- `domain`: Domain name (required)
- `--domains-dir`: Custom domains directory (optional)

**Example**:
```bash
ragdiff init tafsir
```

#### `ragdiff run`
Execute a query set against a provider.

**Parameters**:
- `domain`: Domain name (required)
- `provider`: Provider name (required)
- `query-set`: Query set name (required)
- `--domains-dir`: Custom domains directory (optional)
- `--concurrency`: Parallel execution threads (default: 10)
- `--timeout`: Query timeout in seconds (optional)
- `--format`: Output format: table, json, markdown (default: table)
- `--output`: Save output to file (optional)
- `--quiet`: Suppress progress output (optional)

**Example**:
```bash
ragdiff run tafsir vectara-mmr basic-test --concurrency 10
```

#### `ragdiff compare`
Compare multiple runs using LLM evaluation.

**Parameters**:
- `domain`: Domain name (required)
- `run-ids`: List of run IDs (required, 2+)
- `--domains-dir`: Custom domains directory (optional)
- `--model`: Override LLM model (optional)
- `--temperature`: Override temperature (optional)
- `--concurrency`: Max concurrent evaluations (default: 5)
- `--format`: Output format: table, json, markdown (default: table)
- `--output`: Save output to file (optional)
- `--quiet`: Suppress progress output (optional)

**Example**:
```bash
# Sequential evaluation (backward compatible)
ragdiff compare tafsir run1 run2

# Parallel evaluation (recommended for large query sets)
ragdiff compare tafsir run1 run2 --concurrency 10

# With output file
ragdiff compare tafsir run1 run2 --format markdown --output report.md
```

#### `ragdiff generate-provider`
Generate provider configuration from OpenAPI specification.

**Parameters**:
- `spec`: OpenAPI spec URL or file path (required)
- `--output`: Output file path (optional)
- `--model`: LLM model for analysis (default: gpt-4o)

**Example**:
```bash
ragdiff generate-provider https://api.example.com/openapi.json \
  --output domains/tafsir/providers/example-api.yaml
```

### Public Python API

The v2.0+ public API is exported from `src/ragdiff/__init__.py`:

#### Execution API
```python
from ragdiff import execute_run

run = execute_run(
    domain="tafsir",
    provider="vectara-default",
    query_set="basic-questions"
)
```

#### Comparison API
```python
from ragdiff import compare_runs

comparison = compare_runs(
    domain="tafsir",
    run_ids=[run1.id, run2.id],
    concurrency=10  # Parallel evaluation
)
```

#### Reference Evaluation API
```python
from ragdiff import evaluate_run

evaluation = evaluate_run(
    domain="tafsir",
    run_id=run.id
)
```

#### Provider API
```python
from ragdiff import Provider, create_provider, register_tool

# Create provider from config
provider = create_provider(provider_config)

# Implement custom provider
class MyProvider(Provider):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Implementation
        pass

# Register provider
register_tool("myprovider", MyProvider)
```

## State Management

### Immutable Run State

Runs are immutable snapshots that capture:
- Complete provider configuration at execution time
- Full query set used
- All results with timing information
- Errors and partial failures
- Metadata (timestamps, versions, etc.)

This ensures reproducibility even if configurations change later.

### File-System State

All state is persisted to the file system:
- **Domain Configuration**: `domains/<domain>/domain.yaml`
- **Provider Configs**: `domains/<domain>/providers/*.yaml`
- **Query Sets**: `domains/<domain>/query-sets/*.[txt|jsonl]`
- **Runs**: `domains/<domain>/runs/YYYY-MM-DD/<run-id>.json`
- **Comparisons**: `domains/<domain>/comparisons/YYYY-MM-DD/<comparison-id>.json`

No database required - everything is in YAML/JSON files.

### Registry State

The tool registry maintains singleton state:
- Single instance across application lifetime
- Providers register at module import time
- Thread-safe access to provider classes

## Key Design Decisions

### 1. Domain-Based Organization
**Decision**: Organize everything by problem domain rather than tool/provider.

**Rationale**:
- Natural mental model for experiments
- Clear separation between different problem spaces
- Easy to find related experiments
- Supports different configurations per domain

### 2. Providers = Tool + Configuration
**Decision**: Treat configured tools as first-class "providers".

**Rationale**:
- Enables A/B testing of configurations
- Clear distinction between tool (code) and provider (configured instance)
- Supports multiple configurations of same tool
- Natural versioning through config snapshots

### 3. Immutable Run Snapshots
**Decision**: Store complete configuration snapshots in each run.

**Rationale**:
- Full reproducibility of experiments
- Can modify configs without breaking old runs
- Clear audit trail
- No hidden dependencies

### 4. File-System-First Storage
**Decision**: Use YAML for config, JSON for results, no database.

**Rationale**:
- Simple and transparent
- Version control friendly
- Easy to backup and share
- No infrastructure dependencies
- Human-readable formats

### 5. LiteLLM for Evaluation
**Decision**: Use LiteLLM library for multi-provider LLM support.

**Rationale**:
- Single interface for multiple providers
- Built-in retry logic and error handling
- Cost tracking included
- Easy provider switching
- Active maintenance and updates

### 6. Complete v2.0 Consolidation
**Decision**: Remove all v1.x legacy code in commit c70d340.

**Rationale**:
- Small user base allows clean break
- Eliminates confusion between old/new architecture
- Reduces codebase by ~12,500 lines
- Simpler maintenance and documentation
- Clear versioning boundary

### 7. Singleton Tool Registry
**Decision**: Use singleton pattern for provider registration.

**Rationale**:
- Providers register once at import
- No duplicate registrations
- Global access to available tools
- Thread-safe by design

### 8. Parallel Query Execution
**Decision**: Use ThreadPoolExecutor for concurrent queries.

**Rationale**:
- Significant performance improvement
- Clean abstraction with futures
- Per-query error isolation
- Progress tracking support

### 9. Parallel Evaluation (Spec 0007)
**Decision**: Add parallel evaluation support with configurable concurrency.

**Rationale**:
- Large query sets (100+) require 1.6-8.3 minutes sequentially
- 10x+ speedup with parallel evaluation
- Backward compatible (default concurrency=1)
- Consistent with parallel run execution
- ThreadPoolExecutor handles I/O-bound LLM calls efficiently

### 10. Terminology: "Provider" vs "System"
**Decision**: Use "provider" throughout codebase and documentation.

**Rationale**:
- More natural terminology for RAG services
- Distinguishes from "system" as generic term
- Aligns with industry terminology (OpenAI provider, etc.)
- Clearer intent: these are service providers

## Integration Points

### RAG Providers

#### Vectara
- **Protocol**: HTTP REST API
- **Authentication**: API key header
- **Features**: Corpus search, reranking options (MMR, Slingshot)
- **Configuration**: corpus_id, reranking mode

#### MongoDB Atlas
- **Protocol**: MongoDB wire protocol
- **Authentication**: Connection URI
- **Features**: Vector search with embeddings
- **Dependencies**: OpenAI for embeddings

#### Agentset
- **Protocol**: Python client library
- **Authentication**: API token + namespace
- **Features**: Knowledge graph retrieval
- **Configuration**: namespace_id, reranking

#### Goodmem
- **Protocol**: HTTP REST API
- **Authentication**: API key
- **Features**: Namespace-based search
- **Configuration**: api_key, namespace_id

#### FAISS
- **Protocol**: Local in-memory or file-based
- **Authentication**: None (local)
- **Features**: Vector search with various distance metrics
- **Dependencies**: sentence-transformers for embeddings

#### BM25
- **Protocol**: Local in-memory
- **Authentication**: None (local)
- **Features**: Text-based ranking (no embeddings)
- **Configuration**: k1, b parameters

#### OpenAPI (Generic)
- **Protocol**: HTTP REST API (any)
- **Authentication**: Bearer, API Key, Basic
- **Features**: Zero-code integration via JMESPath mapping
- **Configuration**: AI-generated from OpenAPI specs

### LLM Providers (via LiteLLM)

#### Anthropic Claude
- **Models**: claude-3-5-sonnet-20241022, etc.
- **Authentication**: ANTHROPIC_API_KEY
- **Usage**: Primary evaluation model

#### OpenAI GPT
- **Models**: gpt-4o, gpt-4o-mini, o1-preview, etc.
- **Authentication**: OPENAI_API_KEY
- **Usage**: Alternative evaluation, embeddings

#### Google Gemini
- **Models**: gemini-pro, gemini-1.5-pro, etc.
- **Authentication**: GEMINI_API_KEY
- **Usage**: Cost-effective evaluation

#### Azure OpenAI
- **Models**: Deployed GPT models
- **Authentication**: Azure credentials
- **Usage**: Enterprise deployments

## Development Patterns

### Adding a New Provider

1. Create provider implementation:
```python
# src/ragdiff/providers/myprovider.py
from .abc import Provider
from ..core.models import RetrievedChunk

class MyProvider(Provider):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Implementation
        results = self._call_api(query, top_k)
        return [
            RetrievedChunk(
                content=r["text"],
                score=r["score"],
                metadata={"source": r["source"]}
            )
            for r in results
        ]

# Register at module level
from .registry import register_tool
register_tool("myprovider", MyProvider)
```

2. Import in `providers/__init__.py`:
```python
from . import myprovider  # Triggers registration
```

3. Create provider configuration:
```yaml
# domains/tafsir/providers/myprovider-default.yaml
name: myprovider-default
tool: myprovider
config:
  api_key: ${MYPROVIDER_API_KEY}
  endpoint: https://api.myprovider.com
  timeout: 30
```

### Creating a New Domain

1. Create domain directory structure:
```bash
ragdiff init mydomain
# Or manually:
mkdir -p domains/mydomain/{providers,query-sets,runs,comparisons}
```

2. Create domain configuration:
```yaml
# domains/mydomain/domain.yaml
name: mydomain
description: My domain description
variables:
  default_timeout: 30
secrets:
  anthropic_key: ${ANTHROPIC_API_KEY}
evaluator:
  model: claude-3-5-sonnet-20241022
  temperature: 0.0
  prompt_template: |
    Compare the following RAG results...
```

3. Add providers and query sets:
```bash
# Add provider configs
vim domains/mydomain/providers/vectara.yaml

# Add queries
vim domains/mydomain/query-sets/test.txt
```

### Running Experiments

1. Execute query set:
```bash
ragdiff run mydomain vectara test
```

2. Run multiple providers:
```bash
ragdiff run mydomain vectara test
ragdiff run mydomain mongodb test
ragdiff run mydomain bm25 test
```

3. Compare results:
```bash
ragdiff compare mydomain run1 run2 run3 --concurrency 10
```

## File Naming Conventions

### Configuration Files
- **Domain config**: `domain.yaml` (always this name)
- **Provider configs**: `<descriptive-name>.yaml` (e.g., `vectara-mmr.yaml`)
- **Query sets**: `<name>.txt` or `<name>.jsonl`

### Result Files
- **Runs**: `YYYY-MM-DD/<uuid>.json` (date-organized)
- **Comparisons**: `YYYY-MM-DD/<uuid>.json` (date-organized)

### Python Modules
- **Snake_case**: All Python files (e.g., `models.py`)
- **No underscores in packages**: Directory names avoid underscores
- **Test prefix**: Test files start with `test_`

## Performance Characteristics

### Query Execution
- **Parallelism**: Default 10 concurrent queries
- **Timeout**: Configurable per provider (default 30s)
- **Memory**: ~1KB per query result
- **Scaling**: Tested with 1000 queries per run

### Storage
- **Run size**: ~5-50KB per run (depending on results)
- **Comparison size**: ~10-100KB (depending on runs)
- **File I/O**: JSON parsing optimized with Pydantic

### LLM Evaluation
- **Latency**: 1-3 seconds per query evaluation
- **Parallelism**: Configurable concurrency (default: 5)
- **Performance**: 10x+ speedup with concurrency=10 for 100+ queries
- **Retries**: Exponential backoff (3 attempts)
- **Cost**: ~$0.01-0.05 per comparison (varies by model)
- **Rate limits**: Handled by LiteLLM

## Testing Strategy

### Test Coverage

**Core Tests** (`test_core.py`):
- Domain, ProviderConfig, QuerySet models
- Query validation
- Path utilities
- Serialization

**Provider Tests** (`test_providers.py`):
- Provider interface compliance
- Mock provider implementations
- Factory and registry

**Execution Tests** (`test_execution.py`):
- Parallel query execution
- Error handling
- Progress tracking

**Comparison Tests** (`test_comparison.py`):
- LLM evaluation (mocked)
- Parallel evaluation correctness
- Result formatting

**CLI Tests** (`test_cli.py`):
- Command parsing
- File I/O
- Error handling

**SQuAD Demo Tests** (`test_squad_demo.py`):
- End-to-end demo validation
- Notebook execution

### Test Patterns

**Mock Providers**: Test implementations that return predefined results
**Fixture Data**: Sample domains, configs, and query sets
**Environment Isolation**: Tests use temporary directories
**LLM Mocking**: Mock LiteLLM responses for deterministic tests

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/ragdiff --cov-report=html

# Run specific test file
pytest tests/test_core.py -v

# Run specific test
pytest tests/test_core.py::test_domain_validation -v
```

## Security Considerations

### Credential Management
- **Environment variables**: Never stored in configs
- **Placeholder preservation**: ${VAR_NAME} kept in snapshots
- **Runtime resolution**: Credentials resolved only at execution
- **No logging**: Credentials never logged

### File System Security
- **Permissions**: Standard Unix file permissions apply
- **Sensitive data**: Keep domains/ directory secure
- **Git ignore**: Add domains/*/runs/ and domains/*/comparisons/ to .gitignore

### LLM API Security
- **API keys**: Stored in environment only
- **Rate limiting**: Handled by providers
- **Cost tracking**: Monitor via LiteLLM

## Version History

### v2.1.2 (2025-10-30) - Complete v2.0 Consolidation
**Breaking Change**: Removed all v1.x legacy code

**Major Changes**:
- Removed entire `adapters/` directory (replaced by `providers/`)
- Deleted old `api.py` and v1.x configuration system
- Consolidated `models_v2.py` into main `models.py`
- Removed duplicate evaluation and comparison engines
- Cleaned up 17 obsolete test files
- Renamed `test_cli_v2.py` → `test_cli.py` and `test_core_v2.py` → `test_core.py`
- Moved `openapi_mapping.py` → `providers/openapi_utils.py`
- Updated public API to export domain-based architecture
- Simplified documentation to focus on v2.0+ only
- Fixed pre-commit hook to run all tests

**Impact**:
- Reduced codebase by ~12,500 lines
- Eliminated confusion between old/new architecture
- Clearer terminology: "providers" throughout
- Simpler maintenance

### v2.1.1 (2025-10-26) - SQuAD Demo & Import Fixes
**Enhancement**: SQuAD dataset demo and v2.0 import cleanup

**Changes**:
- Added comprehensive SQuAD demo with Jupyter notebook
- Fixed v2.0 import issues in public API
- Added test coverage for SQuAD demo

### v2.1.0 (2025-10-26) - OpenAPI Provider & Init Command
**Enhancement**: Zero-code integration and easy domain setup

**Major Changes**:
- Generic OpenAPI provider for any REST API
- JMESPath-based response mapping engine
- OpenAPI 3.x specification parser
- AI-powered configuration generator using LiteLLM
- CLI command: `generate-provider` for auto-config generation
- CLI command: `init` for domain setup
- Support for Bearer, API Key, and Basic authentication
- Renamed `generate-adapter` to `generate-provider` for consistency

**New Components**:
- `providers/openapi.py` - Generic OpenAPI provider
- `providers/openapi_utils.py` - JMESPath response mapping
- `openapi/` package - Spec parsing and AI generation

**Dependencies Added**:
- `jmespath>=1.0.1` - JSON query language

### v2.0.1 (2025-10-26) - Evaluation Parallelization (Spec 0007)
**Enhancement**: Parallel LLM evaluation for faster comparisons

**Major Changes**:
- Added `concurrency` parameter to `compare_runs()`
- Parallel evaluation using ThreadPoolExecutor
- CLI `--concurrency` flag (default: 5)
- Real-time progress reporting for evaluations
- 10x+ speedup for large query sets
- Backward compatible (default concurrency=1)

**New Features**:
- `_evaluate_queries_parallel()` function
- `_evaluate_queries_sequential()` function
- Progress callback: `(current, total, successes, failures)`

### v2.0.0 (2025-10-25) - Domain-Based Architecture
**Breaking Change**: Complete architectural rewrite

**Major Changes**:
- Domain-first organization model
- Providers = Tool + Configuration concept
- Immutable run snapshots for reproducibility
- LiteLLM integration for multi-provider support
- File-system-first storage (YAML/JSON)
- New CLI with run/compare commands
- No backwards compatibility with v1.x

**Components**:
- 5 core models in models.py
- 8 provider implementations
- Parallel execution engine
- LLM comparison evaluator
- Comprehensive test suite

### v1.2.1 (Previous) - Adapter-Based Architecture
**Status**: Completely removed in v2.1.2

## Future Enhancements

### Planned Features

1. **Additional Providers**
   - Pinecone vector database
   - Weaviate integration
   - Elasticsearch
   - ChromaDB

2. **Query Set Management**
   - Query set validation and linting
   - Automatic query generation
   - Query difficulty scoring
   - Query clustering and analysis

3. **Advanced Evaluation**
   - Multi-criteria evaluation
   - Custom evaluation prompts per domain
   - Human-in-the-loop evaluation
   - Evaluation caching

4. **Visualization**
   - Web UI for results browsing
   - Comparison charts and graphs
   - Performance trending over time
   - Interactive result exploration

5. **Experiment Tracking**
   - MLflow integration
   - Weights & Biases support
   - Custom metrics tracking
   - Experiment versioning

6. **Performance Improvements**
   - Async execution for I/O operations
   - Result caching
   - Incremental evaluation
   - Streaming results

---

**Document Status**: Complete for v2.1.2
**Last Updated**: 2025-10-30
**Architecture Version**: 2.1.2 (v2.0 Consolidation Complete)
**Maintained By**: Architecture Documenter Agent
