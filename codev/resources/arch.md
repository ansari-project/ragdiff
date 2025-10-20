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
- **pytest**: 7.4.0+ (Testing framework)
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
│   │   ├── 0003-agentset-adapter.md
│   │   └── 0004-adapter-variants.md
│   ├── plans/                  # Implementation plans
│   │   └── 0001-rag-comparison-harness.md
│   └── reviews/                # Code reviews and evaluations
│       └── 0001-rag-comparison-harness.md
├── src/                        # Source code (PYTHONPATH=src)
│   ├── __init__.py
│   ├── __main__.py            # Entry point for python -m src
│   └── ragdiff/               # Main package
│       ├── __init__.py
│       ├── cli.py             # Typer CLI implementation
│       ├── core/              # Core models and configuration
│       │   ├── __init__.py
│       │   ├── models.py      # Data models (RagResult, ComparisonResult, etc.)
│       │   └── config.py      # YAML configuration management
│       ├── adapters/          # RAG tool adapters
│       │   ├── __init__.py
│       │   ├── base.py        # BaseRagTool (SearchVectara interface)
│       │   ├── factory.py     # Adapter factory and registry
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
├── tests/                     # Test suite (90+ tests)
│   ├── test_cli.py
│   ├── test_adapters.py
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
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/core/models.py`
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
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/core/config.py`
- **Purpose**: Load and validate YAML configuration with environment variable substitution
- **Key Class**: `Config`
  - Loads YAML configuration from `configs/` directory
  - Processes `${ENV_VAR}` placeholders with actual environment values
  - Validates tool configurations and credentials
  - Methods:
    - `get_tool_config(tool_name)`: Retrieve specific tool configuration
    - `get_llm_config()`: Get LLM evaluation settings
    - `validate()`: Ensure all required environment variables are set

### 3. Base Adapter (`src/ragdiff/adapters/base.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/adapters/base.py`
- **Purpose**: Abstract base class implementing SearchVectara interface
- **Key Class**: `BaseRagTool(SearchVectara)`
  - Ensures compatibility with Ansari Backend
  - Provides normalized search interface
  - Handles credential validation and error handling
  - Methods:
    - `run(query, **kwargs)`: SearchVectara-compatible search method
    - `format_as_tool_result(results)`: Format for tool display
    - `search(query, top_k)`: Abstract method for subclasses to implement
    - `_normalize_score(score)`: Normalize scores to 0-1 range
  - Attributes: `name`, `timeout`, `max_retries`, `default_top_k`

### 4. Adapter Factory (`src/ragdiff/adapters/factory.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/adapters/factory.py`
- **Purpose**: Registry pattern for creating and managing adapters
- **Key Components**:
  - `ADAPTER_REGISTRY`: Dict mapping adapter names to classes
    - Registered adapters: `vectara`, `tafsir`, `mawsuah`, `goodmem`, `agentset`
  - `create_adapter(tool_name, config)`: Factory method for adapter creation
    - Supports adapter variants via `config.adapter` field
    - Enables multiple configurations of same adapter (e.g., "agentset-rerank-on" and "agentset-rerank-off")
  - `register_adapter(name, adapter_class)`: Add new adapter to registry
  - `get_available_adapters()`: List registered adapter names

### 5. Tool Adapters

#### Vectara Adapter (`src/ragdiff/adapters/vectara.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/adapters/vectara.py`
- **Purpose**: Connect to Vectara v2 API for corpus search
- **Implementation**:
  - Uses Vectara v2 API (`/v2/query` endpoint)
  - Supports different corpora via `corpus_key` configuration
  - Extracts metadata from both part and document levels
  - Handles optional summary results
  - Methods:
    - `search(query, top_k)`: Execute Vectara search
    - `format_as_ref_list(results)`: Format as Claude reference list

#### Goodmem Adapter (`src/ragdiff/adapters/goodmem.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/adapters/goodmem.py`
- **Purpose**: Connect to Goodmem RAG platform
- **Implementation**:
  - Uses goodmem-client Python library
  - Configurable space_ids for different knowledge bases
  - Supports both streaming and CLI API modes
  - Fallback mechanism for API failures

#### Agentset Adapter (`src/ragdiff/adapters/agentset.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/adapters/agentset.py`
- **Purpose**: Connect to Agentset RAG-as-a-Service platform
- **Implementation**:
  - Uses Agentset SDK (agentset-python)
  - Requires both API token and namespace ID
  - Supports rerank option via `config.options.rerank`
  - Handles SearchData response format with `.data` attribute
  - Methods:
    - `search(query, top_k)`: Execute semantic search
    - Extracts metadata: filename, filetype, file_directory, sequence_number, languages

### 6. Comparison Engine (`src/ragdiff/comparison/engine.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/comparison/engine.py`
- **Purpose**: Orchestrate parallel or sequential RAG tool searches
- **Key Class**: `ComparisonEngine`
  - Manages multiple tool adapters
  - Executes searches with configurable parallelism
  - Collects latency and error metrics
  - Methods:
    - `run_comparison(query, top_k, parallel)`: Run query across all tools
    - `_run_parallel(query, top_k)`: ThreadPoolExecutor-based parallel execution
    - `_run_sequential(query, top_k)`: Sequential execution for debugging
    - `_run_single_search(tool_name, tool, query, top_k)`: Single search with timing
    - `get_summary_stats(result)`: Calculate performance statistics

### 7. LLM Evaluator (`src/ragdiff/evaluation/evaluator.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/evaluation/evaluator.py`
- **Purpose**: Use Claude to provide qualitative RAG result evaluation
- **Key Class**: `LLMEvaluator`
  - Uses Anthropic Claude API for evaluation
  - Supports multiple Claude models (default: claude-sonnet-4-20250514)
  - Evaluates on 5 dimensions: Relevance, Completeness, Accuracy, Coherence, Source Quality
  - Methods:
    - `evaluate(result)`: Evaluate ComparisonResult and return LLMEvaluation
    - `_build_evaluation_prompt(result)`: Construct structured evaluation prompt
    - `_parse_evaluation(analysis_text, result)`: Parse Claude response into structured data
  - Display name mapping: Maps internal names (tafsir, goodmem) to display names (vectara, goodmem)

### 8. Display Formatter (`src/ragdiff/display/formatter.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/display/formatter.py`
- **Purpose**: Format comparison results in multiple output formats
- **Key Class**: `ComparisonFormatter`
  - Supports 5 output formats: display, json, markdown, summary, csv/jsonl
  - Text wrapping and indentation for readability
  - Methods:
    - `format_side_by_side(result)`: Human-friendly side-by-side comparison
    - `format_json(result, pretty)`: JSON output with optional pretty-printing
    - `format_markdown(result)`: Markdown formatted output
    - `format_summary(result)`: Brief one-line summary
    - Helper methods: `_format_header()`, `_format_errors()`, `_format_results_comparison()`, `_format_performance()`, `_format_llm_evaluation()`

### 9. CLI (`src/ragdiff/cli.py`)
- **Location**: `/Users/mwk/Development/ansari-project/ragdiff/src/ragdiff/cli.py`
- **Purpose**: Typer-based command-line interface with Rich formatting
- **Commands**:
  - `compare`: Single query comparison across tools
    - Options: `--tool`, `--top-k`, `--config`, `--format`, `--output`, `--parallel`, `--evaluate`, `--verbose`
  - `batch`: Batch processing of queries from file
    - Options: `--tool`, `--top-k`, `--config`, `--output-dir`, `--format`, `--evaluate`, `--verbose`
    - Generates: Individual results (JSON/JSONL/CSV) + holistic summary (Markdown)
  - `list-tools`: List available and configured tools
  - `validate-config`: Validate YAML configuration
  - `quick-test`: Run quick test query to verify setup
- **Helper Functions**:
  - `_display_rich_results(result)`: Rich panel-based result display
  - `_display_llm_evaluation(evaluation)`: Format LLM evaluation with emoji
  - `_display_batch_latency_stats(results, tool_names)`: Percentile statistics (P50, P95, P99)
  - `_display_llm_evaluation_summary(results, tool_names)`: Win counts and average quality scores
  - `_generate_and_display_holistic_summary(results, tool_names, output_file)`: Comprehensive markdown summary
  - `_display_stats_table(stats)`: Performance metrics table

## Data Flow

### Single Query Comparison Flow
```
1. User Input (CLI)
   └─> compare command with query and options

2. Configuration Loading
   └─> Config reads YAML file
   └─> Validates environment variables
   └─> Creates ToolConfig objects

3. Adapter Creation
   └─> Factory creates adapters from configs
   └─> Each adapter validates credentials

4. Comparison Execution
   └─> ComparisonEngine.run_comparison()
   └─> Parallel/Sequential execution
   └─> Each adapter.search() returns List[RagResult]
   └─> Engine collects results + errors + latency

5. Optional LLM Evaluation
   └─> LLMEvaluator.evaluate(result)
   └─> Build prompt with all tool results
   └─> Claude API call
   └─> Parse response into LLMEvaluation

6. Output Formatting
   └─> ComparisonFormatter formats result
   └─> Display/JSON/Markdown/Summary/CSV

7. Display to User
   └─> Rich console output or file save
```

### Batch Processing Flow
```
1. Load Queries from File
   └─> Read line-by-line from input file

2. Initialize Tools Once
   └─> Config + Factory + ComparisonEngine

3. For Each Query:
   └─> Run comparison
   └─> Optional LLM evaluation
   └─> Collect results in memory

4. Aggregate Statistics
   └─> Latency percentiles (P50, P95, P99)
   └─> Win counts and quality scores
   └─> Issue tracking (duplicates, fragmentation, citations)

5. Generate Outputs
   └─> Individual results (JSONL/CSV/JSON)
   └─> Holistic summary (Markdown)
   └─> Terminal display with Rich tables

6. Save to Output Directory
   └─> Timestamped files in outputs/
```

### Adapter Variant Flow
```
1. YAML Configuration
   tool-variant-name:
     adapter: agentset        # Which adapter class to use
     options:                 # Custom configuration
       rerank: true

2. Config Parser
   └─> Creates ToolConfig with name="tool-variant-name"
   └─> Sets config.adapter="agentset"
   └─> Sets config.options={"rerank": true}

3. Factory
   └─> Uses config.adapter (not tool_name) to lookup class
   └─> Creates AgentsetAdapter instance
   └─> Adapter reads config.options for custom settings

4. Adapter Execution
   └─> Uses self.rerank from config.options
   └─> Executes search with variant-specific behavior

5. Results Display
   └─> Uses tool_name (YAML key) for display
   └─> User sees "tool-variant-name" in results
```

## Configuration Architecture

### YAML Configuration Structure
```yaml
tools:
  # Standard tool configuration
  vectara:
    api_key_env: VECTARA_API_KEY
    corpus_id: ${VECTARA_CORPUS_ID}
    base_url: https://api.vectara.io
    timeout: 30

  # Adapter variant configuration
  agentset-rerank-on:
    adapter: agentset              # Which adapter class to use
    api_key_env: AGENTSET_API_TOKEN
    namespace_id_env: AGENTSET_NAMESPACE_ID
    options:                       # Custom adapter options
      rerank: true
    timeout: 60
    default_top_k: 10

llm:
  model: claude-opus-4-1-20250805  # Or claude-sonnet-4-20250514
  api_key_env: ANTHROPIC_API_KEY
```

### Environment Variables
Required environment variables (set in `.env`):
- `VECTARA_API_KEY`: Vectara platform API key
- `VECTARA_CORPUS_ID`: Vectara corpus ID (or use corpus_id in YAML)
- `GOODMEM_API_KEY`: Goodmem API key
- `AGENTSET_API_TOKEN`: Agentset API token
- `AGENTSET_NAMESPACE_ID`: Agentset namespace ID
- `ANTHROPIC_API_KEY`: Claude API key for LLM evaluation

## Key Design Decisions

### 1. Adapter Pattern for Extensibility
**Decision**: Use adapter pattern with factory registry instead of hardcoded tool integrations.

**Rationale**:
- Easy to add new RAG tools without modifying core comparison logic
- Clean separation of concerns between comparison engine and tool-specific code
- Enables testing with mock adapters

**Implementation**: `BaseRagTool` abstract class + `ADAPTER_REGISTRY` in factory.

### 2. SearchVectara Interface Compatibility
**Decision**: All adapters inherit from SearchVectara base class and implement `run()` and `format_as_tool_result()`.

**Rationale**:
- Enables seamless integration with Ansari Backend
- Maintains compatibility with existing Ansari tools
- Provides familiar interface for Ansari developers

**Tradeoff**: SearchVectara interface designed for Vectara, requires some workarounds for other platforms (e.g., Agentset doesn't use corpus_id).

### 3. Normalized RagResult Data Model
**Decision**: All adapters convert their native response formats to unified `RagResult` structure.

**Rationale**:
- Enables fair comparison across different platforms
- Simplifies display and evaluation logic
- Hides platform-specific response structures

**Tradeoff**: Some platform-specific metadata may be lost in normalization.

### 4. Optional LLM Evaluation
**Decision**: Make LLM evaluation opt-in via `--evaluate` flag instead of always-on.

**Rationale**:
- LLM API calls cost money and add latency
- Not always needed for quick comparisons
- Users can choose when to pay for qualitative analysis

**Implementation**: `--evaluate` flag in CLI + conditional evaluator instantiation.

### 5. Adapter Variants via YAML
**Decision**: Support multiple configurations of same adapter via YAML key + `adapter` field.

**Rationale**:
- Enable A/B testing without code changes (e.g., rerank on vs off)
- Compare different corpora from same platform
- Flexible configuration without hardcoding variants in factory

**Implementation**: `config.adapter` field overrides YAML key for factory lookup.

### 6. Parallel Search Execution
**Decision**: Use ThreadPoolExecutor for parallel tool searches with configurable parallel/sequential mode.

**Rationale**:
- Faster total comparison time when searching multiple tools
- Each tool's API call is I/O-bound, perfect for threading
- Sequential mode available for debugging

**Tradeoff**: Thread safety considerations for adapter implementations.

### 7. Percentile Latency Metrics
**Decision**: Report P50, P95, P99 latencies instead of just averages in batch mode.

**Rationale**:
- Percentiles reveal consistency and worst-case performance
- More useful for production decision-making than averages
- Industry standard for performance metrics

**Implementation**: Only available in batch mode (need multiple data points).

### 8. Holistic Summary Generation
**Decision**: Generate comprehensive markdown summaries for batch evaluations with query-by-query breakdowns, common themes, and overall verdicts.

**Rationale**:
- Provides actionable insights beyond raw data
- Identifies patterns across multiple queries
- Supports production adoption decisions

**Implementation**: `_generate_and_display_holistic_summary()` with theme tracking and issue analysis.

### 9. Subjective Quality Over Metrics
**Decision**: Focus on LLM-based subjective quality evaluation instead of quantitative overlap metrics.

**Rationale**:
- User feedback indicated subjective quality is more important for decision-making
- Metrics like overlap@k don't capture coherence, completeness, or source quality
- Claude can evaluate dimensions that matter for user experience

**Tradeoff**: LLM evaluations are slower and cost money, but provide more actionable insights.

### 10. Fail-Fast Credential Validation
**Decision**: Validate all credentials at startup before running comparisons.

**Rationale**:
- Immediate feedback if configuration is incorrect
- Avoids partial comparison failures
- Clear error messages guide users to fix issues

**Implementation**: `Config.validate()` checks all environment variables before adapter creation.

## Integration Points

### External Services

#### Vectara Platform (HTTP API)
- **Endpoint**: `https://api.vectara.io/v2/query`
- **Authentication**: `x-api-key` header
- **Protocol**: REST API with JSON payloads
- **Response Format**: `search_results` array with `text`, `score`, `document_id`, metadata
- **Adapter**: `VectaraAdapter`

#### Goodmem (Python Client)
- **Library**: `goodmem-client>=1.5.5`
- **Authentication**: API key via client initialization
- **Protocol**: Python SDK with streaming and CLI modes
- **Configuration**: Configurable space_ids for different knowledge bases
- **Adapter**: `GoodmemAdapter`

#### Agentset (Python SDK)
- **Library**: `agentset>=0.4.0`
- **Authentication**: Token + namespace ID
- **Protocol**: Python SDK with `.data` attribute pattern
- **Methods**: `client.search.execute(query, top_k, include_metadata, mode)`
- **Response**: `SearchResponse` with `.data` containing `List[SearchData]`
- **Adapter**: `AgentsetAdapter`

#### Anthropic Claude (HTTP API)
- **Library**: `anthropic>=0.25.0`
- **Authentication**: API key via environment variable
- **Models**: claude-opus-4-1-20250805, claude-sonnet-4-20250514
- **Protocol**: Messages API with structured prompts
- **Usage**: LLM-based quality evaluation
- **Component**: `LLMEvaluator`

### Ansari Backend Integration
- **Interface**: SearchVectara compatibility layer
- **Methods**: `run(query, **kwargs)`, `format_as_tool_result(results)`
- **Purpose**: Enable direct import of adapters into Ansari
- **Path**: Adapters can be packaged and imported as library

## Development Patterns

### 1. Adding a New RAG Tool Adapter

**Steps**:
1. Create adapter class in `src/ragdiff/adapters/`
```python
from .base import BaseRagTool
from ..core.models import RagResult

class MyToolAdapter(BaseRagTool):
    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        # 1. Call tool-specific API
        # 2. Convert response to RagResult objects
        # 3. Return list of normalized results
        pass
```

2. Register in factory (`src/ragdiff/adapters/factory.py`):
```python
from .mytool import MyToolAdapter

ADAPTER_REGISTRY["mytool"] = MyToolAdapter
```

3. Add configuration in `configs/tools.yaml`:
```yaml
tools:
  mytool:
    api_key_env: MYTOOL_API_KEY
    base_url: https://api.mytool.com
    timeout: 30
```

4. Set environment variable:
```bash
export MYTOOL_API_KEY=your_api_key
```

5. Test the adapter:
```bash
uv run rag-compare compare "test query" --tool mytool
```

### 2. Creating Adapter Variants

**Use Case**: Compare same tool with different configurations

**Configuration**:
```yaml
mytool-config-a:
  adapter: mytool           # Which adapter class
  api_key_env: MYTOOL_API_KEY
  options:
    setting: value_a        # Custom option A

mytool-config-b:
  adapter: mytool           # Same adapter class
  api_key_env: MYTOOL_API_KEY
  options:
    setting: value_b        # Custom option B
```

**Adapter Implementation**:
```python
def __init__(self, config: ToolConfig):
    super().__init__(config)
    # Read custom options
    if config.options:
        self.setting = config.options.get('setting', 'default')
```

### 3. Batch Processing Workflow

**Input File Format** (`inputs/queries.txt`):
```
What is Islamic inheritance law?
Explain the concept of tawhid
When should I pray Fajr?
```

**Command**:
```bash
uv run rag-compare batch inputs/queries.txt \
  --config configs/tafsir.yaml \
  --evaluate \
  --top-k 10 \
  --format jsonl
```

**Output Files**:
- `outputs/batch_results_20250514_120000.jsonl`: Individual query results
- `outputs/holistic_summary_20250514_120000.md`: Comprehensive summary

### 4. Custom LLM Evaluation Prompts

**Location**: `src/ragdiff/evaluation/evaluator.py`

**Method**: `_build_evaluation_prompt(result)`

**Customization Points**:
- Evaluation dimensions (currently: Relevance, Completeness, Accuracy, Coherence, Source Quality)
- Quality score scale (currently: 0-100)
- Output format instructions
- Display name mapping (for tool name normalization)

### 5. Error Handling Pattern

**Philosophy**: Fail fast with clear error messages, no silent fallbacks

**Implementation**:
```python
# Credential validation at adapter initialization
if not os.getenv(config.api_key_env):
    raise ValueError(
        f"Missing required environment variable: {config.api_key_env}\n"
        f"Please set it with your {config.name} API key."
    )

# API call error handling
try:
    response = api_call()
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    logger.error(f"API request failed: {str(e)}")
    raise  # No fallback, fail fast
```

### 6. Testing Pattern

**Test Organization**:
- `tests/test_cli.py`: CLI command testing
- `tests/test_adapters.py`: Adapter functionality
- `tests/test_engine.py`: Comparison engine
- `tests/test_formatter.py`: Output formatting

**Mock Pattern**:
```python
from unittest.mock import Mock, patch

@patch('ragdiff.adapters.vectara.requests.post')
def test_vectara_search(mock_post):
    mock_post.return_value.json.return_value = {
        'search_results': [...]
    }
    adapter = VectaraAdapter(config)
    results = adapter.search("query", top_k=5)
    assert len(results) == 5
```

## File Naming Conventions

### Python Modules
- **Lowercase with underscores**: `comparison_engine.py`, `base_adapter.py`
- **Package markers**: `__init__.py` in all package directories
- **Entry points**: `__main__.py` for `python -m` support

### Configuration Files
- **Lowercase with hyphens**: `tafsir.yaml`, `mawsuah.yaml`
- **Descriptive names**: Name reflects purpose (e.g., `tafsir.yaml` for Tafsir corpus comparison)

### Documentation Files
- **Markdown**: `.md` extension
- **Numbered specs**: `0001-feature-name.md`, `0002-feature-name.md`
- **Descriptive names**: `architecture.md`, `holistic_summary_20250514_120000.md`

### Output Files
- **Timestamped**: `batch_results_YYYYMMDD_HHMMSS.jsonl`
- **Format suffix**: `.jsonl`, `.csv`, `.json`, `.md`
- **Descriptive prefix**: `batch_results_`, `holistic_summary_`

## Common Operations

### Run Single Comparison
```bash
uv run rag-compare compare "Your query" \
  --tool vectara --tool goodmem \
  --top-k 10 \
  --format markdown \
  --output results.md
```

### Run with LLM Evaluation
```bash
uv run rag-compare compare "Your query" \
  --evaluate \
  --config configs/tafsir.yaml
```

### Batch Processing
```bash
uv run rag-compare batch inputs/queries.txt \
  --config configs/tafsir.yaml \
  --evaluate \
  --top-k 10 \
  --output-dir outputs \
  --format jsonl
```

### List Available Tools
```bash
uv run rag-compare list-tools --config configs/tafsir.yaml
```

### Validate Configuration
```bash
uv run rag-compare validate-config --config configs/tafsir.yaml
```

### Quick Test
```bash
uv run rag-compare quick-test --config configs/tafsir.yaml
```

## Performance Considerations

### Latency Optimization
- **Parallel Execution**: Use `--parallel` (default) for multi-tool comparisons
- **ThreadPoolExecutor**: I/O-bound API calls benefit from threading
- **Top-K Limits**: Lower `--top-k` values reduce API response times

### Cost Optimization
- **Optional LLM Eval**: Use `--evaluate` only when needed (costs per query)
- **Batch Processing**: Amortize setup costs across many queries
- **Model Selection**: claude-sonnet-4 cheaper than claude-opus-4

### Memory Management
- **Streaming JSONL**: Batch mode writes results incrementally
- **Result Limits**: Top-K limits prevent excessive memory usage
- **Generator Patterns**: Could be added for very large batches

## Future Architecture Considerations

Based on specs and reviews, potential future enhancements:

### RAG System Generalization (Spec 0002)
- Support for LangChain, LlamaIndex, Haystack frameworks
- HTTP endpoint adapter for custom RAG services
- Local/self-hosted system support
- Custom response format mappers

### Testing Infrastructure
- Comprehensive test coverage (currently at 90+)
- Integration tests for all adapters
- Performance benchmarking suite

### Advanced Features
- Result caching for repeated queries
- Web UI for non-CLI users
- Progress persistence for interrupted batch runs
- Parallel LLM evaluation calls
- Custom evaluation criteria
- Diff highlighting in display mode

### Integration Enhancements
- CI/CD pipeline integration
- Automated regression testing
- Production monitoring hooks

---

**Document Status**: Current as of 2025-10-20
**Project Version**: 0.1.0
**Last Updated**: Architecture review based on implementation, specs, and plans
**Next Review**: After significant architectural changes or new component additions
