# RAGDiff

A flexible framework for comparing Retrieval-Augmented Generation (RAG) systems side-by-side, with support for subjective quality evaluation using LLMs.

## Features

- **Multi-tool Support**: Compare multiple RAG tools in parallel
- **Flexible Adapters**: Easy-to-extend adapter pattern for adding new tools
- **Multiple Output Formats**: Display, JSON, Markdown, and summary formats
- **Performance Metrics**: Automatic latency measurement and result statistics
- **LLM Evaluation**: Support for subjective quality assessment using Claude 4.1 Opus
- **Rich CLI**: Beautiful terminal output with tables and panels
- **Comprehensive Testing**: 90+ tests ensuring reliability

## Installation

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

To install uv:
```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Or with pip
pip install uv
```

### Setup

```bash
# Clone the repository
git clone https://github.com/ansari-project/ragdiff.git
cd ragdiff

# Install dependencies with uv
uv sync --all-extras  # Install all dependencies including dev tools

# Or install only core dependencies
uv sync

# Or install with goodmem support
uv sync --extra goodmem

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Create a `configs/tools.yaml` file:

```yaml
tools:
  # Vectara platform (can use different corpus names: vectara, tafsir, mawsuah)
  vectara:
    api_key_env: VECTARA_API_KEY
    corpus_id: ${VECTARA_CORPUS_ID}
    base_url: https://api.vectara.io
    timeout: 30

  goodmem:
    api_key_env: GOODMEM_API_KEY
    base_url: https://api.goodmem.ai
    timeout: 30

  agentset:
    api_key_env: AGENTSET_API_TOKEN
    namespace_id_env: AGENTSET_NAMESPACE_ID
    timeout: 60

llm:
  model: claude-opus-4-1-20250805
  api_key_env: ANTHROPIC_API_KEY
```

### Adapter Variants

RAGDiff supports adapter variants, allowing you to compare different configurations of the same RAG tool. This is useful for A/B testing different settings (e.g., reranking on vs off) without code changes.

**Configuration Format:**

```yaml
tools:
  # Variant 1: Agentset with reranking enabled
  agentset-rerank-on:
    adapter: agentset           # Which adapter class to use
    api_key_env: AGENTSET_API_TOKEN
    namespace_id_env: AGENTSET_NAMESPACE_ID
    options:                    # Custom adapter-specific options
      rerank: true
    timeout: 60
    default_top_k: 10

  # Variant 2: Agentset with reranking disabled
  agentset-rerank-off:
    adapter: agentset           # Same adapter, different config
    api_key_env: AGENTSET_API_TOKEN
    namespace_id_env: AGENTSET_NAMESPACE_ID
    options:
      rerank: false
    timeout: 60
    default_top_k: 10

  # Variant 3: Vectara with different corpus
  tafsir-corpus:
    adapter: vectara            # Use vectara adapter
    api_key_env: VECTARA_API_KEY
    corpus_id: tafsir_v1
    timeout: 30

  mawsuah-corpus:
    adapter: vectara            # Same adapter, different corpus
    api_key_env: VECTARA_API_KEY
    corpus_id: mawsuah_v1
    timeout: 30
```

**Key Concepts:**

- **YAML key**: Becomes the display name in results (e.g., `agentset-rerank-on`)
- **adapter field**: Specifies which adapter class to use (defaults to YAML key if omitted)
- **options dict**: Custom configuration passed to the adapter

**Usage Example:**

```bash
# Compare two agentset variants
uv run rag-compare compare "Your query" \
  --tool agentset-rerank-on \
  --tool agentset-rerank-off \
  --config configs/my-variants.yaml
```

**Backward Compatibility:**

Existing configurations without the `adapter` field continue to work. The adapter name defaults to the YAML key:

```yaml
# This still works - adapter defaults to "vectara"
vectara:
  api_key_env: VECTARA_API_KEY
  corpus_id: my_corpus
```

## Usage

RAGDiff can be used both as a **CLI tool** and as a **Python library**. Choose the interface that best fits your workflow.

### Library API

Use RAGDiff programmatically in your Python applications for maximum flexibility and integration.

#### Installation as a Library

```bash
# Install from source
cd ragdiff
uv pip install -e .

# Or in your project
pip install ragdiff  # When published to PyPI
```

#### Quick Start

```python
from ragdiff import query, compare, run_batch

# Single query against one tool
results = query("config.yaml", "What is RAG?", tool="vectara", top_k=5)
for result in results:
    print(f"{result.score:.3f}: {result.text[:100]}")

# Compare multiple tools
comparison = compare(
    "config.yaml",
    "What is RAG?",
    tools=["vectara", "goodmem"],
    top_k=5,
    evaluate=True  # Run LLM evaluation
)
print(f"Winner: {comparison.llm_evaluation.winner}")
print(f"Vectara score: {comparison.llm_evaluation.quality_scores['vectara']}")

# Batch processing
queries = ["What is RAG?", "What is vector search?", "Explain embeddings"]
results = run_batch(
    "config.yaml",
    queries,
    tools=["vectara", "goodmem"],
    parallel=True,
    evaluate=True
)
for result in results:
    print(f"Query: {result.query}")
    print(f"Winner: {result.llm_evaluation.winner if result.llm_evaluation else 'N/A'}")
```

#### Core Functions

**`query(config_path, query_text, tool, top_k=5)`**

Run a single query against one RAG system.

```python
from ragdiff import query

results = query(
    config_path="config.yaml",
    query_text="What is Islamic inheritance law?",
    tool="vectara",
    top_k=10
)

for idx, result in enumerate(results, 1):
    print(f"{idx}. [{result.score:.3f}] {result.text[:200]}")
    print(f"   Source: {result.source}")
```

**`compare(config_path, query_text, tools=None, top_k=5, parallel=True, evaluate=False)`**

Compare multiple RAG systems on a single query.

```python
from ragdiff import compare

comparison = compare(
    config_path="config.yaml",
    query_text="Explain Quranic inheritance",
    tools=["vectara", "goodmem", "agentset"],  # None = all tools
    top_k=5,
    parallel=True,  # Run searches in parallel
    evaluate=True   # Run LLM evaluation
)

# Access results
print(f"Query: {comparison.query}")
print(f"Tools compared: {list(comparison.tool_results.keys())}")

for tool_name, results in comparison.tool_results.items():
    print(f"\n{tool_name}: {len(results)} results")
    if results:
        print(f"  Top result: {results[0].text[:100]}")

# LLM evaluation (if evaluate=True)
if comparison.llm_evaluation:
    print(f"\nWinner: {comparison.llm_evaluation.winner}")
    print(f"Analysis: {comparison.llm_evaluation.analysis}")
    for tool, score in comparison.llm_evaluation.quality_scores.items():
        print(f"  {tool}: {score}/100")
```

**`run_batch(config_path, queries, tools=None, top_k=5, parallel=True, evaluate=False)`**

Run multiple queries against multiple RAG systems.

```python
from ragdiff import run_batch

queries = [
    "What is zakat?",
    "Explain hajj requirements",
    "What is the shahada?"
]

results = run_batch(
    config_path="config.yaml",
    queries=queries,
    tools=["vectara", "goodmem"],
    top_k=5,
    parallel=True,
    evaluate=True
)

# Process results
for comparison in results:
    print(f"\nQuery: {comparison.query}")
    print(f"Results: {comparison.get_result_counts()}")

    if comparison.llm_evaluation:
        print(f"Winner: {comparison.llm_evaluation.winner}")
        print(f"Scores: {comparison.llm_evaluation.quality_scores}")
```

**`evaluate_with_llm(comparison_result, model=None, api_key=None)`**

Evaluate comparison results using an LLM.

```python
from ragdiff import compare, evaluate_with_llm

# Run comparison without evaluation
comparison = compare("config.yaml", "What is RAG?", tools=["vectara", "goodmem"])

# Evaluate later
evaluation = evaluate_with_llm(
    comparison,
    model="claude-sonnet-4-20250514",  # Optional, uses config default
    api_key=None  # Optional, uses ANTHROPIC_API_KEY env var
)

print(f"Winner: {evaluation.winner}")
print(f"Analysis: {evaluation.analysis}")
```

#### Configuration Management

```python
from ragdiff import load_config, validate_config, get_available_adapters

# Load and validate configuration
config = load_config("config.yaml")
validate_config("config.yaml")

# Get available adapters
adapters = get_available_adapters()
for adapter_name, info in adapters.items():
    print(f"{adapter_name}: {info['description']}")
    print(f"  Required env vars: {info['required_env_vars']}")
```

#### Working with Results

```python
from ragdiff import compare
from ragdiff.core.serialization import to_json

comparison = compare("config.yaml", "test query", tools=["vectara"])

# Convert to JSON
json_output = to_json(comparison, pretty=True)
print(json_output)

# Convert to dict
data = comparison.to_dict()

# Access specific fields
print(f"Query: {comparison.query}")
print(f"Timestamp: {comparison.timestamp}")
print(f"Errors: {comparison.errors}")
print(f"Has errors: {comparison.has_errors()}")
```

#### Thread-Safe Usage

RAGDiff is thread-safe and can be used in multi-threaded applications:

```python
from concurrent.futures import ThreadPoolExecutor
from ragdiff import query

def run_query(query_text):
    return query("config.yaml", query_text, tool="vectara", top_k=5)

# Safe concurrent execution
with ThreadPoolExecutor(max_workers=10) as executor:
    queries = [f"Query {i}" for i in range(100)]
    results = list(executor.map(run_query, queries))

print(f"Completed {len(results)} queries concurrently")
```

#### Error Handling

```python
from ragdiff import query, compare
from ragdiff.core.errors import (
    ConfigurationError,
    AdapterError,
    ValidationError,
    EvaluationError
)

try:
    results = query("config.yaml", "test", tool="invalid_tool")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except AdapterError as e:
    print(f"Adapter failed: {e}")
except ValidationError as e:
    print(f"Invalid input: {e}")

# Errors are also captured in comparison results
comparison = compare("config.yaml", "test", tools=["vectara", "goodmem"])
if comparison.has_errors():
    for tool, error in comparison.errors.items():
        print(f"{tool} failed: {error}")
```

#### FastAPI Integration

See `examples/fastapi_integration.py` for a complete FastAPI service example:

```bash
# Install FastAPI dependencies
uv pip install fastapi uvicorn

# Run the API server
uvicorn examples.fastapi_integration:app --reload

# Or run directly
python examples/fastapi_integration.py
```

The example includes:
- Thread-safe concurrent request handling
- Structured JSON request/response models
- Comprehensive error handling
- Configuration validation on startup
- Health check endpoint
- API documentation at `/docs`

**Example API calls:**

```bash
# Health check
curl http://localhost:8000/health

# Query single tool
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "tool": "vectara", "top_k": 5}'

# Compare multiple tools
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "tools": ["vectara", "goodmem"], "evaluate": true}'

# Batch queries
curl -X POST http://localhost:8000/batch \
  -H "Content-Type: application/json" \
  -d '{"queries": ["What is RAG?", "Explain vectors"], "tools": ["vectara"]}'
```

### CLI Usage

For command-line usage, RAGDiff provides a rich CLI interface.

#### Basic Comparison

```bash
# Compare all configured tools
uv run rag-compare compare "What is Islamic inheritance law?"

# Compare specific tools
uv run rag-compare compare "Your query" --tool vectara --tool goodmem --tool agentset

# Adjust number of results
uv run rag-compare compare "Your query" --top-k 10
```

### Output Formats

```bash
# Default display format (side-by-side)
uv run rag-compare compare "Your query"

# JSON output
uv run rag-compare compare "Your query" --format json

# Markdown output
uv run rag-compare compare "Your query" --format markdown

# Summary output
uv run rag-compare compare "Your query" --format summary

# Save to file
uv run rag-compare compare "Your query" --output results.json --format json
```

### Batch Comparison with LLM Evaluation

Run multiple queries and get comprehensive analysis:

```bash
# Basic batch comparison
uv run rag-compare batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --top-k 10 \
  --format json

# With LLM evaluation (generates holistic summary)
uv run rag-compare batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --evaluate \
  --top-k 10 \
  --format json

# Custom output directory
uv run rag-compare batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --evaluate \
  --output-dir my-results \
  --format jsonl
```

The batch command with `--evaluate` generates:
- Individual query results in JSON/JSONL/CSV format
- Latency statistics (P50, P95, P99)
- LLM evaluation summary showing wins and quality scores
- **Holistic summary** (markdown file) with:
  - Query-by-query breakdown with winners and scores
  - Common themes: win distribution, recurring issues
  - Key differentiators: what makes winner better vs loser weaknesses
  - Overall verdict with production recommendation

**Example: 3-Way Tafsir Comparison (Vectara vs Goodmem vs Agentset)**

```bash
# Compare all three RAG systems with LLM evaluation
uv run rag-compare batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --evaluate \
  --top-k 10
```

This runs 6 test queries across Vectara, Goodmem, and Agentset, evaluating:
- Performance: Latency and response times
- Quality: LLM-scored relevance and coherence (0-100)
- Issues: Fragmentation, citations, completeness

Results saved to `outputs/batch_results_TIMESTAMP.jsonl` and `outputs/holistic_summary_TIMESTAMP.md`

Convert holistic summary to PDF:
```bash
# Generate PDF from markdown summary
python md2pdf.py outputs/holistic_summary_TIMESTAMP.md
```

### Other Commands

```bash
# List available tools
uv run rag-compare list-tools

# Validate configuration
uv run rag-compare validate-config

# Run quick test
uv run rag-compare quick-test

# Get help
uv run rag-compare --help
uv run rag-compare compare --help
uv run rag-compare batch --help
```

## Project Structure

```
ragdiff/
├── src/
│   ├── core/           # Core models and configuration
│   │   ├── models.py    # Data models (RagResult, ComparisonResult, etc.)
│   │   └── config.py    # Configuration management
│   ├── adapters/        # Tool adapters
│   │   ├── base.py      # Base adapter implementing SearchVectara interface
│   │   ├── vectara.py   # Vectara platform adapter
│   │   ├── goodmem.py   # Goodmem adapter with mock fallback
│   │   ├── agentset.py  # Agentset adapter
│   │   └── factory.py   # Adapter factory
│   ├── comparison/      # Comparison engine
│   │   └── engine.py    # Parallel/sequential search execution
│   ├── display/         # Display formatters
│   │   └── formatter.py # Multiple output format support
│   └── cli.py          # Typer CLI implementation
├── tests/              # Comprehensive test suite
├── configs/            # Configuration files
└── requirements.txt    # Python dependencies
```

## Architecture

The tool follows the SPIDER protocol for systematic development:

1. **Specification**: Clear goals for subjective RAG comparison
2. **Planning**: Phased implementation approach
3. **Implementation**: Clean architecture with separation of concerns
4. **Defense**: Comprehensive test coverage (90+ tests)
5. **Evaluation**: Expert review and validation
6. **Commit**: Version control with clear history

### Key Components

- **BaseRagTool**: Abstract base implementing SearchVectara interface
- **Adapters**: Tool-specific implementations (Vectara, Goodmem, Agentset)
- **ComparisonEngine**: Orchestrates parallel/sequential searches
- **ComparisonFormatter**: Handles multiple output formats
- **Config**: Manages YAML configuration with environment variables

## Adding New RAG Tools

1. Create a new adapter in `src/adapters/`:

```python
from .base import BaseRagTool
from ..core.models import RagResult

class MyToolAdapter(BaseRagTool):
    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        # Implement tool-specific search
        results = self.client.search(query, limit=top_k)
        return [self._convert_to_rag_result(r) for r in results]
```

2. Register in `src/adapters/factory.py`:

```python
ADAPTER_REGISTRY["mytool"] = MyToolAdapter
```

3. Add configuration in `configs/tools.yaml`:

```yaml
tools:
  mytool:
    api_key_env: MYTOOL_API_KEY
    base_url: https://api.mytool.com
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_cli.py

# Run with coverage
uv run pytest tests/ --cov=src
```

### Code Style

The project uses:
- Black for formatting
- Ruff for linting
- MyPy for type checking

```bash
# Format code with Black
uv run black src/ tests/

# Check linting with Ruff
uv run ruff check src/ tests/

# Type checking with MyPy
uv run mypy src/
```

## Environment Variables

Required environment variables:

- `VECTARA_API_KEY`: For Vectara platform access
- `VECTARA_CORPUS_ID`: Vectara corpus ID (or use corpus key)
- `GOODMEM_API_KEY`: For Goodmem access (optional, uses mock if not set)
- `AGENTSET_API_TOKEN`: For Agentset access
- `AGENTSET_NAMESPACE_ID`: Agentset namespace ID
- `ANTHROPIC_API_KEY`: For LLM evaluation (optional)

## License

[Your License]

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.

## Acknowledgments

Built following the SPIDER protocol for systematic development.
