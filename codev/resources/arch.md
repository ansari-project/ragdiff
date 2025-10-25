# RAGDiff v2.0 Architecture

## Overview

RAGDiff v2.0 is a domain-centric experimentation framework for comparing Retrieval-Augmented Generation (RAG) systems. The architecture fundamentally shifts from the v1.x adapter-based approach to a domain-first organizational model that treats experiments as first-class objects with full reproducibility and structured comparison capabilities.

Key architectural principles:
- **Domain-Driven Design**: Experiments organized by knowledge domains (tafsir, legal, medical)
- **Systems = Tool + Configuration**: Enable A/B testing of different configurations
- **Immutable Runs**: Timestamped, versioned, and fully reproducible experimental results
- **File-System-First**: All configuration in YAML, all results in JSON
- **LLM-Based Evaluation**: Structured comparison using multiple LLM providers via LiteLLM
- **Clean Separation**: Core models, systems interface, execution engine, and CLI are clearly separated

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

### RAG System Clients
- **requests**: 2.31.0+ (HTTP client for Vectara)
- **agentset**: 0.4.0+ (Agentset RAG platform)
- **pymongo**: 4.0.0+ (MongoDB Atlas Vector Search)
- **openai**: 1.0.0+ (Embeddings for MongoDB)

### Development Tools
- **pytest**: 7.4.0+ (Testing framework with 78+ v2.0 tests)
- **pytest-cov**: 4.1.0+ (Coverage reporting)
- **ruff**: 0.1.0+ (Fast Python linter and formatter)
- **pre-commit**: 3.0.0+ (Git hooks for code quality)

## Directory Structure

```
ragdiff/
├── src/ragdiff/                    # Main package (v2.0 architecture)
│   ├── __init__.py                 # Package initialization
│   ├── __main__.py                 # Entry point for python -m ragdiff
│   ├── cli.py                      # Main CLI entry (38 lines, imports cli_v2)
│   ├── cli_v2.py                   # v2.0 CLI implementation (run, compare commands)
│   ├── version.py                  # Version information
│   │
│   ├── core/                       # Core data models and utilities
│   │   ├── models_v2.py            # v2.0 Pydantic models
│   │   ├── loaders.py              # YAML and text file loading
│   │   ├── storage.py              # JSON persistence utilities
│   │   ├── env_vars.py             # Environment variable handling
│   │   ├── paths.py                # Path utilities
│   │   └── logging.py              # Logging configuration
│   │
│   ├── systems/                    # RAG system implementations (v2.0)
│   │   ├── __init__.py             # Auto-imports for registration
│   │   ├── abc.py                  # System abstract base class
│   │   ├── registry.py             # Singleton tool registry
│   │   ├── factory.py              # System factory with validation
│   │   ├── vectara.py              # Vectara system implementation
│   │   ├── mongodb.py              # MongoDB Atlas system
│   │   └── agentset.py             # Agentset system
│   │
│   ├── execution/                  # Query execution engine
│   │   ├── __init__.py
│   │   └── executor.py             # RunExecutor with parallel execution
│   │
│   ├── comparison/                 # LLM-based comparison
│   │   ├── __init__.py
│   │   └── evaluator.py            # ComparisonEvaluator using LiteLLM
│   │
│   ├── display/                    # Output formatting
│   │   └── formatter.py            # Table, JSON, Markdown formatters
│   │
│   ├── adapters/                   # Legacy v1.x adapters (deprecated)
│   └── api.py                      # Legacy v1.x API (deprecated)
│
├── tests/                          # Test suite
│   ├── test_core_v2.py             # Core models tests (29 tests)
│   ├── test_systems.py             # System implementations (29 tests)
│   ├── test_execution.py           # Execution engine tests (12 tests)
│   ├── test_comparison.py          # Comparison tests (5 tests)
│   ├── test_cli_v2.py              # CLI tests (8 tests)
│   └── [legacy v1.x test files]
│
├── domains/                        # Domain experiment directories
│   └── <domain-name>/              # e.g., tafsir, legal, medical
│       ├── domain.yaml             # Domain configuration
│       ├── systems/                # System configurations
│       │   └── <system-name>.yaml  # e.g., vectara-mmr.yaml
│       ├── query-sets/             # Query collections
│       │   ├── <name>.txt         # Plain text queries
│       │   └── <name>.jsonl       # Queries with references
│       ├── runs/                   # Execution results
│       │   └── YYYY-MM-DD/        # Date-organized runs
│       │       └── <run-id>.json  # Run results
│       └── comparisons/            # Comparison results
│           └── <comparison-id>.json
│
├── configs/                        # Legacy v1.x configs (deprecated)
├── pyproject.toml                  # Package configuration
├── README.md                       # User documentation
└── CLAUDE.md                       # Development instructions
```

## Core Components

### 1. Data Models (`src/ragdiff/core/models_v2.py`)

**Location**: `src/ragdiff/core/models_v2.py`
**Purpose**: Define v2.0 data structures using Pydantic for validation and serialization

#### Key Classes

**Domain**:
- Represents a knowledge area (e.g., tafsir, legal, medical)
- Fields: `name`, `description`, `variables`, `secrets`, `evaluator`, `metadata`
- Scopes all experiments within a problem space
- Loaded from `domains/<domain>/domain.yaml`

**SystemConfig**:
- Configuration for a RAG system (tool + settings)
- Fields: `name`, `tool`, `config`, `metadata`
- Enables multiple configurations of same tool
- Loaded from `domains/<domain>/systems/<name>.yaml`

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
- Single retrieved text chunk from a RAG system
- Fields: `content`, `score`, `metadata` (source_id, doc_id, chunk_id)
- Normalized output format across all systems

**QueryResult**:
- Result for a single query execution
- Fields: `query`, `retrieved`, `reference`, `duration_ms`, `error`
- Captures both successful results and failures

**Run**:
- Complete execution: QuerySet × System
- Fields: `id`, `domain`, `system`, `query_set`, `status`, `results`, `system_config`, `query_set_snapshot`, `started_at`, `completed_at`, `metadata`
- Statuses: `pending`, `running`, `completed`, `failed`, `partial`
- Stores complete snapshots for reproducibility
- Saved to `domains/<domain>/runs/YYYY-MM-DD/<run-id>.json`

**Comparison**:
- Multi-run comparison with LLM evaluation
- Fields: `id`, `domain`, `runs`, `evaluations`, `timestamp`, `evaluator_config`, `metadata`
- Contains per-query evaluations with winner determination

**LLMEvaluation**:
- Individual query evaluation result
- Fields: `query`, `reference`, `run_results`, `winner`, `analysis`, `scores`, `metadata`
- Structured output from LLM comparison

### 2. File Loaders (`src/ragdiff/core/loaders.py`)

**Location**: `src/ragdiff/core/loaders.py`
**Purpose**: Load configuration and query files from disk

**Key Functions**:

`load_domain(domain_path: Path) -> Domain`:
- Loads domain.yaml configuration
- Preserves ${VAR_NAME} placeholders for security
- Validates domain structure

`load_system_config(config_path: Path) -> SystemConfig`:
- Loads system YAML configuration
- Validates tool references
- Preserves environment variables

`load_query_set(query_set_path: Path, domain_name: str) -> QuerySet`:
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

**Location**: `src/ragdiff/core/storage.py`
**Purpose**: Persist runs and comparisons to JSON

**Key Functions**:

`save_run(run: Run, output_dir: Path) -> Path`:
- Saves run to date-organized directory
- Creates `runs/YYYY-MM-DD/<run-id>.json`
- Returns saved file path

`load_run(run_path: Path) -> Run`:
- Loads run from JSON file
- Validates and reconstructs Run object

`save_comparison(comparison: Comparison, output_dir: Path) -> Path`:
- Saves comparison results
- Creates `comparisons/<comparison-id>.json`

`load_comparison(comparison_path: Path) -> Comparison`:
- Loads comparison from JSON
- Reconstructs Comparison object

### 4. System Interface (`src/ragdiff/systems/`)

#### Abstract Base Class (`abc.py`)

**Location**: `src/ragdiff/systems/abc.py`
**Purpose**: Define common interface for all RAG systems

```python
class System(ABC):
    """Abstract base class for RAG systems."""

    def __init__(self, config: dict[str, Any]):
        """Initialize with configuration dictionary."""
        self.config = config
        self._resolve_env_vars()

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search and return ranked chunks."""
        pass

    def _resolve_env_vars(self):
        """Replace ${VAR_NAME} with environment values."""
        # Recursive resolution of environment variables
```

#### Tool Registry (`registry.py`)

**Location**: `src/ragdiff/systems/registry.py`
**Purpose**: Singleton registry for tool registration

**Key Components**:

`ToolRegistry` (Singleton):
- `_instance`: Single registry instance
- `_tools`: Dictionary of registered tools
- Thread-safe singleton pattern

`register_tool(name: str, tool_class: type[System])`:
- Registers tool class with name
- Called at module import time
- Validates tool implements System interface

`get_tool(name: str) -> type[System]`:
- Retrieves registered tool class
- Raises error if not found

`list_tools() -> list[str]`:
- Returns all registered tool names

#### System Factory (`factory.py`)

**Location**: `src/ragdiff/systems/factory.py`
**Purpose**: Create system instances from configuration

`create_system(config: SystemConfig) -> System`:
- Gets tool class from registry
- Instantiates with configuration
- Handles environment variable substitution
- Returns configured System instance

#### System Implementations

**Vectara System** (`vectara.py`):
- HTTP-based API client
- Supports MMR and Slingshot reranking
- Corpus ID configuration
- Score normalization (0-1 range)

**MongoDB System** (`mongodb.py`):
- Atlas Vector Search integration
- Dynamic query embedding via OpenAI
- Configurable field mappings
- Metadata extraction

**Agentset System** (`agentset.py`):
- Namespace-based retrieval
- Optional reranking
- Multi-space support
- Fallback handling

### 5. Execution Engine (`src/ragdiff/execution/executor.py`)

**Location**: `src/ragdiff/execution/executor.py`
**Purpose**: Execute query sets against systems with parallel processing

**Key Class**: `RunExecutor`

**Constructor Parameters**:
- `system`: System instance to execute queries against
- `max_workers`: Number of parallel threads (default: 10)
- `progress_callback`: Optional callback for progress updates

**Main Method**: `execute(query_set: QuerySet) -> Run`
- Creates pending Run object
- Uses ThreadPoolExecutor for parallel queries
- Captures per-query timing and errors
- Updates Run status based on results
- Preserves system config and query set snapshots

**Error Handling**:
- Per-query error isolation
- Partial success support (some queries fail)
- Comprehensive error messages with stack traces

**Progress Tracking**:
- Callback interface: `callback(current: int, total: int, query: str)`
- Real-time progress updates for UI

### 6. Comparison Engine (`src/ragdiff/comparison/evaluator.py`)

**Location**: `src/ragdiff/comparison/evaluator.py`
**Purpose**: Compare runs using LLM evaluation via LiteLLM

**Key Class**: `ComparisonEvaluator`

**Constructor Parameters**:
- `model`: LLM model identifier (e.g., "claude-3-5-sonnet-20241022")
- `api_key`: Optional API key override
- `temperature`: LLM temperature (default: 0.0)
- `max_retries`: Retry count for failures (default: 3)

**Main Method**: `compare(runs: list[Run], domain: Domain) -> Comparison`
- Validates all runs are from same domain
- Aligns queries across runs
- Evaluates each query using LLM
- Returns structured Comparison object

**LLM Integration**:
- Uses LiteLLM for multi-provider support
- Structured prompts for consistent evaluation
- Retry logic with exponential backoff
- Cost tracking via `litellm.completion_cost()`

**Evaluation Process**:
1. Format retrieved chunks for each system
2. Build evaluation prompt with query and results
3. Call LLM for winner determination
4. Parse structured response
5. Calculate quality scores
6. Track costs and metadata

### 7. CLI Interface (`src/ragdiff/cli_v2.py`)

**Location**: `src/ragdiff/cli_v2.py`
**Purpose**: Command-line interface for v2.0 operations

#### Commands

**`run` Command**:
```python
def run(
    domain: str,
    system: str,
    query_set: str,
    output_dir: Optional[Path] = None,
    max_workers: int = 10,
    format: str = "table"
)
```
- Executes query set against system
- Shows Rich progress bar during execution
- Saves run to `domains/<domain>/runs/`
- Displays results in chosen format

**`compare` Command**:
```python
def compare(
    domain: str,
    runs: list[str],
    model: Optional[str] = None,
    output: Optional[Path] = None,
    format: str = "table"
)
```
- Loads specified runs by ID
- Performs LLM evaluation
- Saves comparison results
- Displays winner analysis

**Output Formats**:
- `table`: Rich terminal tables with colors
- `json`: Structured JSON output
- `markdown`: Markdown tables for documentation

### 8. Display Formatting (`src/ragdiff/display/formatter.py`)

**Location**: `src/ragdiff/display/formatter.py`
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

`get_domain_path(domain_name: str) -> Path`:
- Returns path to domain directory
- Creates directory if needed

`get_runs_dir(domain_name: str) -> Path`:
- Returns path to runs directory
- Creates date-organized subdirectories

`get_systems_dir(domain_name: str) -> Path`:
- Returns path to systems configuration directory

`get_query_sets_dir(domain_name: str) -> Path`:
- Returns path to query sets directory

### Logging Configuration (`src/ragdiff/core/logging.py`)

`setup_logging(level: str = "INFO")`:
- Configures structured logging
- Sets up formatters and handlers
- Used for debugging and monitoring

## Data Flow

### Query Execution Flow (v2.0)

```
1. User invokes CLI
   └─> ragdiff run --domain tafsir --system vectara-mmr --query-set basic

2. Load Domain Configuration
   └─> load_domain("domains/tafsir/domain.yaml")
   └─> Domain object with variables and evaluator config

3. Load System Configuration
   └─> load_system_config("domains/tafsir/systems/vectara-mmr.yaml")
   └─> SystemConfig with tool="vectara" and settings

4. Create System Instance
   └─> factory.create_system(system_config)
   └─> Registry lookup for "vectara" tool class
   └─> VectaraSystem instance with resolved env vars

5. Load Query Set
   └─> load_query_set("domains/tafsir/query-sets/basic.txt")
   └─> QuerySet with list of Query objects

6. Execute Queries
   └─> RunExecutor(system).execute(query_set)
   └─> ThreadPoolExecutor for parallel execution
   └─> Progress callbacks to CLI for Rich progress bar
   └─> Capture results and timing per query

7. Save Run
   └─> save_run(run, "domains/tafsir/runs/")
   └─> Creates "runs/2025-10-25/<run-id>.json"
   └─> Includes config snapshots for reproducibility

8. Display Results
   └─> format_run_results(run, format="table")
   └─> Rich terminal table with results
```

### Comparison Flow (v2.0)

```
1. User invokes comparison
   └─> ragdiff compare --domain tafsir --runs run1 run2 run3

2. Load Domain
   └─> load_domain("domains/tafsir/domain.yaml")
   └─> Get evaluator configuration

3. Load Runs
   └─> Find and load each run by ID
   └─> Validate all runs are from same domain
   └─> Check query alignment

4. Create Evaluator
   └─> ComparisonEvaluator(model=domain.evaluator.model)
   └─> Configure LiteLLM with API credentials

5. Evaluate Each Query
   └─> For each aligned query across runs:
       └─> Format retrieved chunks from each system
       └─> Build evaluation prompt
       └─> Call LLM for analysis
       └─> Parse winner and scores
       └─> Handle retries on failure

6. Save Comparison
   └─> save_comparison(comparison, "domains/tafsir/comparisons/")
   └─> Creates "comparisons/<comparison-id>.json"

7. Display Results
   └─> format_comparison_results(comparison, format="table")
   └─> Show winner statistics and analysis
```

## API Structure

### v2.0 CLI Commands

The v2.0 CLI provides two main commands:

#### `ragdiff run`
Execute a query set against a system.

**Parameters**:
- `--domain`: Domain name (required)
- `--system`: System name (required)
- `--query-set`: Query set name (required)
- `--output-dir`: Custom output directory (optional)
- `--max-workers`: Parallel execution threads (default: 10)
- `--format`: Output format: table, json, markdown (default: table)

**Example**:
```bash
ragdiff run --domain tafsir --system vectara-mmr --query-set basic-test
```

#### `ragdiff compare`
Compare multiple runs using LLM evaluation.

**Parameters**:
- `--domain`: Domain name (required)
- `--runs`: List of run IDs (required, 2+)
- `--model`: Override LLM model (optional)
- `--output`: Save comparison to file (optional)
- `--format`: Output format: table, json, markdown (default: table)

**Example**:
```bash
ragdiff compare --domain tafsir --runs run1 run2 --format markdown
```

### Internal Python APIs

While v2.0 is primarily CLI-driven, the internal APIs are well-structured:

#### System Interface
```python
from ragdiff.systems.abc import System
from ragdiff.core.models_v2 import RetrievedChunk

class MySystem(System):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Implementation
        pass
```

#### Execution API
```python
from ragdiff.execution.executor import RunExecutor
from ragdiff.core.models_v2 import QuerySet, Run

executor = RunExecutor(system, max_workers=10)
run: Run = executor.execute(query_set)
```

#### Comparison API
```python
from ragdiff.comparison.evaluator import ComparisonEvaluator
from ragdiff.core.models_v2 import Comparison

evaluator = ComparisonEvaluator(model="claude-3-5-sonnet-20241022")
comparison: Comparison = evaluator.compare(runs, domain)
```

## State Management

### Immutable Run State

Runs are immutable snapshots that capture:
- Complete system configuration at execution time
- Full query set used
- All results with timing information
- Errors and partial failures
- Metadata (timestamps, versions, etc.)

This ensures reproducibility even if configurations change later.

### File-System State

All state is persisted to the file system:
- **Domain Configuration**: `domains/<domain>/domain.yaml`
- **System Configs**: `domains/<domain>/systems/*.yaml`
- **Query Sets**: `domains/<domain>/query-sets/*.[txt|jsonl]`
- **Runs**: `domains/<domain>/runs/YYYY-MM-DD/<run-id>.json`
- **Comparisons**: `domains/<domain>/comparisons/<comparison-id>.json`

No database required - everything is in YAML/JSON files.

### Registry State

The tool registry maintains singleton state:
- Single instance across application lifetime
- Tools register at module import time
- Thread-safe access to tool classes

## Key Design Decisions

### 1. Domain-Based Organization
**Decision**: Organize everything by problem domain rather than tool/adapter.

**Rationale**:
- Natural mental model for experiments
- Clear separation between different problem spaces
- Easy to find related experiments
- Supports different configurations per domain

### 2. Systems = Tool + Configuration
**Decision**: Treat configured tools as first-class "systems".

**Rationale**:
- Enables A/B testing of configurations
- Clear distinction between tool (code) and system (configured instance)
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

### 6. No Backwards Compatibility
**Decision**: v2.0 breaks compatibility with v1.x completely.

**Rationale**:
- Small user base allows clean break
- Fundamental architecture change
- Simpler codebase without legacy support
- Clear versioning boundary

### 7. Singleton Tool Registry
**Decision**: Use singleton pattern for tool registration.

**Rationale**:
- Tools register once at import
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

## Integration Points

### RAG Systems

#### Vectara
- **Protocol**: HTTP REST API
- **Authentication**: API key header
- **Features**: Corpus search, reranking options
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

### LLM Providers (via LiteLLM)

#### Anthropic Claude
- **Models**: claude-3-5-sonnet-20241022, etc.
- **Authentication**: ANTHROPIC_API_KEY
- **Usage**: Primary evaluation model

#### OpenAI GPT
- **Models**: gpt-4o, gpt-4o-mini, etc.
- **Authentication**: OPENAI_API_KEY
- **Usage**: Alternative evaluation

#### Google Gemini
- **Models**: gemini-pro, gemini-1.5-pro, etc.
- **Authentication**: GEMINI_API_KEY
- **Usage**: Cost-effective evaluation

#### Azure OpenAI
- **Models**: Deployed GPT models
- **Authentication**: Azure credentials
- **Usage**: Enterprise deployments

## Development Patterns

### Adding a New System

1. Create system implementation:
```python
# src/ragdiff/systems/mysystem.py
from .abc import System
from ..core.models_v2 import RetrievedChunk

class MySystem(System):
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
register_tool("mysystem", MySystem)
```

2. Import in `systems/__init__.py`:
```python
from . import mysystem  # Triggers registration
```

3. Create system configuration:
```yaml
# domains/tafsir/systems/mysystem-default.yaml
name: mysystem-default
tool: mysystem
config:
  api_key: ${MYSYSTEM_API_KEY}
  endpoint: https://api.mysystem.com
  timeout: 30
```

### Creating a New Domain

1. Create domain directory structure:
```bash
mkdir -p domains/mydomain/{systems,query-sets,runs,comparisons}
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
```

3. Add systems and query sets:
```bash
# Add system configs
vim domains/mydomain/systems/vectara.yaml

# Add queries
vim domains/mydomain/query-sets/test.txt
```

### Running Experiments

1. Execute query set:
```bash
ragdiff run --domain mydomain --system vectara --query-set test
```

2. Run multiple systems:
```bash
ragdiff run --domain mydomain --system vectara --query-set test
ragdiff run --domain mydomain --system mongodb --query-set test
```

3. Compare results:
```bash
ragdiff compare --domain mydomain --runs run1 run2
```

## File Naming Conventions

### Configuration Files
- **Domain config**: `domain.yaml` (always this name)
- **System configs**: `<descriptive-name>.yaml` (e.g., `vectara-mmr.yaml`)
- **Query sets**: `<name>.txt` or `<name>.jsonl`

### Result Files
- **Runs**: `YYYY-MM-DD/<uuid>.json` (date-organized)
- **Comparisons**: `<uuid>.json` (flat structure)

### Python Modules
- **Snake_case**: All Python files (e.g., `models_v2.py`)
- **No underscores in packages**: Directory names avoid underscores
- **Test prefix**: Test files start with `test_`

## Performance Characteristics

### Query Execution
- **Parallelism**: Default 10 concurrent queries
- **Timeout**: Configurable per system (default 30s)
- **Memory**: ~1KB per query result
- **Scaling**: Tested with 1000 queries per run

### Storage
- **Run size**: ~5-50KB per run (depending on results)
- **Comparison size**: ~10-100KB (depending on runs)
- **File I/O**: JSON parsing optimized with Pydantic

### LLM Evaluation
- **Latency**: 1-3 seconds per query evaluation
- **Retries**: Exponential backoff (3 attempts)
- **Cost**: ~$0.01-0.05 per comparison (varies by model)
- **Rate limits**: Handled by LiteLLM

## Testing Strategy

### Test Coverage (v2.0)

**Unit Tests** (78 total):
- `test_core_v2.py`: 29 tests for data models
- `test_systems.py`: 29 tests for system implementations
- `test_execution.py`: 12 tests for execution engine
- `test_comparison.py`: 5 tests for LLM evaluation
- `test_cli_v2.py`: 8 tests for CLI commands

### Test Patterns

**Mock Systems**: Test implementations that return predefined results
**Fixture Data**: Sample domains, configs, and query sets
**Environment Isolation**: Tests use temporary directories
**LLM Mocking**: Mock LiteLLM responses for deterministic tests

### Running Tests

```bash
# Run all v2.0 tests
pytest tests/test_*_v2.py tests/test_systems.py tests/test_execution.py

# Run with coverage
pytest tests/ --cov=src/ragdiff --cov-report=html

# Run specific test file
pytest tests/test_core_v2.py -v
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
- **Git ignore**: Add domains/*/runs/ to .gitignore

### LLM API Security
- **API keys**: Stored in environment only
- **Rate limiting**: Handled by providers
- **Cost tracking**: Monitor via LiteLLM

## Version History

### v2.0.0 (2025-10-25) - Domain-Based Architecture
**Breaking Change**: Complete architectural rewrite

**Major Changes**:
- Domain-first organization model
- Systems = Tool + Configuration concept
- Immutable run snapshots for reproducibility
- LiteLLM integration for multi-provider support
- File-system-first storage (YAML/JSON)
- New CLI with only run/compare commands
- No backwards compatibility with v1.x

**Components**:
- 5 core models in models_v2.py
- 3 system implementations
- Parallel execution engine
- LLM comparison evaluator
- 78 comprehensive tests

### v1.2.1 (Previous) - Adapter-Based Architecture
**Status**: Deprecated, replaced by v2.0

## Future Enhancements

### Planned Features

1. **Additional Systems**
   - Pinecone vector database
   - Weaviate integration
   - Custom REST API adapter

2. **Query Set Management**
   - Query set validation and linting
   - Automatic query generation
   - Query difficulty scoring

3. **Advanced Evaluation**
   - Multi-criteria evaluation
   - Custom evaluation prompts
   - Human-in-the-loop evaluation

4. **Visualization**
   - Web UI for results browsing
   - Comparison charts and graphs
   - Performance trending

5. **Experiment Tracking**
   - MLflow integration
   - Weights & Biases support
   - Custom metrics tracking

---

**Document Status**: Complete for v2.0.0
**Last Updated**: 2025-10-25
**Architecture Version**: 2.0.0 (Domain-Based)
**Maintained By**: Architecture Documenter Agent