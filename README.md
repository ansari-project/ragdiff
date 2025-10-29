# RAGDiff v2.0

A domain-based framework for comparing Retrieval-Augmented Generation (RAG) systems with LLM evaluation support.

## Explanatory Video

<div align="center">
  <a href="https://www.youtube.com/watch?v=DVtkj1BC-oY">
    <img src="https://img.youtube.com/vi/DVtkj1BC-oY/maxresdefault.jpg" alt="RAGDiff Explained" width="80%">
  </a>
  <br>
  <em>📹 Click to watch: In-depth explanation of RAGDiff and how it works</em>
</div>

<br>

## AI Assistant Integration

RAGDiff includes structured documentation for both humans and AI assistants:

### For AI Assistants

We provide [llmstxt](https://llmstxt.org/) files to help AI assistants understand the codebase:

- **[llms.txt](llms.txt)** - Quick project overview for AI assistants
- **[llms-full.txt](llms-full.txt)** - Comprehensive documentation including architecture, workflow, and implementation details

These files follow the llmstxt.org specification and enable AI assistants (like Claude, ChatGPT, or Cursor) to quickly understand how to use and contribute to RAGDiff. If you're using an AI assistant to work with this codebase, point it to these files first!

### For Developers

- **[GUIDE.md](GUIDE.md)** - Complete configuration guide explaining directory structure, YAML formats, and best practices

## What's New in v2.0

RAGDiff v2.0 introduces a **domain-based architecture** that organizes RAG system comparison around problem domains:

- **Domains**: Separate workspaces for different problem areas (e.g., tafsir, legal, medical)
- **Systems**: RAG system configurations that can be version-controlled
- **Query Sets**: Reusable collections of test queries
- **Runs**: Reproducible executions with config snapshots
- **Comparisons**: LLM-based evaluations with detailed analysis

This replaces the v1.x adapter-based approach with a more structured, reproducible workflow perfect for systematic RAG system development and A/B testing.

## Features

- **Domain-Driven Organization**: Separate workspaces for different problem domains
- **Reproducible Runs**: Config and query set snapshots for full reproducibility
- **Multi-System Support**: Compare Vectara, MongoDB, Agentset, and more
- **LLM Evaluation**: Subjective quality assessment via LiteLLM (GPT, Claude, Gemini)
- **Rich CLI**: Beautiful terminal output with progress bars and summary tables
- **Multiple Output Formats**: Table, JSON, and Markdown reports
- **Comprehensive Testing**: 78 tests ensuring reliability
- **Parallel Execution**: Fast query execution with configurable concurrency

## Installation

### From PyPI (Recommended)

RAGDiff is now available on PyPI and can be installed with either pip or uv:

```bash
# Using pip
pip install ragdiff

# Using uv (faster)
uv pip install ragdiff
```

### From Source (Development)

#### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver (optional but recommended)

To install uv:
```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Or with pip
pip install uv
```

#### Setup

```bash
# Clone the repository
git clone https://github.com/ansari-project/ragdiff.git
cd ragdiff

# Option 1: Install with uv (recommended)
uv sync --all-extras  # Install all dependencies including dev tools
uv pip install -e .   # Install in editable mode

# Option 2: Install with pip
pip install -e .      # Install in editable mode

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys
```

## Quick Start

### 1. Create a Domain

The easiest way to get started is using the init command (coming soon):

```bash
# Initialize a new domain (planned feature)
ragdiff init my-domain --template default
```

Until the init command is available, create the structure manually:

```bash
# Create domain directory structure
mkdir -p domains/my-domain/{systems,query-sets,runs,comparisons}

# Create domain config
cat > domains/my-domain/domain.yaml <<EOF
name: my-domain
description: My RAG comparison domain
evaluator:
  model: gpt-4
  temperature: 0.0
  prompt_template: |
    Compare these RAG results for relevance and accuracy.
    Query: {query}

    Results:
    {results}

    Provide winner and analysis.
EOF
```

### 2. Configure Systems

```bash
# Create Vectara system config
cat > domains/my-domain/systems/vectara-default.yaml <<EOF
name: vectara-default
tool: vectara
config:
  api_key: \${VECTARA_API_KEY}
  corpus_id: \${VECTARA_CORPUS_ID}
  timeout: 30
EOF

# Create MongoDB system config
cat > domains/my-domain/systems/mongodb-local.yaml <<EOF
name: mongodb-local
tool: mongodb
config:
  connection_uri: \${MONGODB_URI}
  database: my_db
  collection: documents
  index_name: vector_index
  embedding_model: all-MiniLM-L6-v2
  timeout: 60
EOF
```

### 3. Create Query Sets

```bash
# Create test queries
cat > domains/my-domain/query-sets/test-queries.txt <<EOF
What is machine learning?
Explain neural networks
How does backpropagation work?
EOF
```

### 4. Run Comparisons

```bash
# Execute query sets against different systems
uv run ragdiff run my-domain vectara-default test-queries
uv run ragdiff run my-domain mongodb-local test-queries

# Compare the runs (use run IDs from output or check domains/my-domain/runs/)
uv run ragdiff compare my-domain <run-id-1> <run-id-2>

# Export comparison to different formats
uv run ragdiff compare my-domain <run-id-1> <run-id-2> --format markdown --output report.md
uv run ragdiff compare my-domain <run-id-1> <run-id-2> --format json --output comparison.json
```

## Example Output

RAGDiff generates comprehensive comparison reports in multiple formats. Here's what the output looks like:

- **Table Format**: Beautiful terminal output with colored statistics
- **JSON Format**: Machine-readable results for programmatic analysis
- **Markdown Format**: Human-readable reports with detailed evaluations

[View Example Markdown Output](examples/squad-demo/comparison_results.md) - See a real comparison between FAISS providers with different embedding models.

The reports include:
- Provider win/loss/tie statistics
- Average quality scores
- Query-by-query evaluation details
- LLM reasoning for each comparison
- Performance metrics (latency, tokens used)

## CLI Commands

RAGDiff v2.0 provides two main CLI commands:

### `run` - Execute Query Sets

Execute a query set against a system:

```bash
# Basic usage
uv run ragdiff run <domain> <system> <query-set>

# Examples
uv run ragdiff run tafsir vectara-default test-queries
uv run ragdiff run tafsir mongodb-local test-queries --concurrency 5

# With options
uv run ragdiff run tafsir vectara-default test-queries \
  --domains-dir ./domains \
  --concurrency 10 \
  --timeout 30 \
  --quiet
```

**What it does:**
- Loads system config from `domains/<domain>/systems/<system>.yaml`
- Loads queries from `domains/<domain>/query-sets/<query-set>.txt`
- Executes all queries with progress bar
- Saves results to `domains/<domain>/runs/<run-id>.json`
- Displays summary table

**Options:**
- `--concurrency N`: Max concurrent queries (default: 10)
- `--timeout N`: Timeout per query in seconds (default: 30.0)
- `--domains-dir PATH`: Custom domains directory (default: ./domains)
- `--quiet`: Suppress progress output

### `compare` - Evaluate Runs

Compare multiple runs using LLM evaluation:

```bash
# Basic usage
uv run ragdiff compare <domain> <run-id-1> <run-id-2> [<run-id-3> ...]

# Examples
uv run ragdiff compare tafsir abc123 def456
uv run ragdiff compare tafsir abc123 def456 --format json --output comparison.json

# With options
uv run ragdiff compare tafsir abc123 def456 \
  --model gpt-4 \
  --temperature 0.0 \
  --format markdown \
  --output report.md
```

**What it does:**
- Loads runs from `domains/<domain>/runs/`
- Uses LLM (via LiteLLM) for evaluation
- Saves comparison to `domains/<domain>/comparisons/<comparison-id>.json`
- Outputs in specified format

**Output formats:**
- `table`: Rich console table (default)
- `json`: JSON output
- `markdown`: Markdown report

**Options:**
- `--model MODEL`: Override LLM model
- `--temperature N`: Override temperature
- `--format FORMAT`: Output format (table, json, markdown)
- `--output PATH`: Save to file
- `--domains-dir PATH`: Custom domains directory
- `--quiet`: Suppress progress output

## Domain Directory Structure

```
domains/
├── tafsir/                    # Domain: Islamic tafsir
│   ├── domain.yaml            # Domain config (evaluator settings)
│   ├── systems/               # System configurations
│   │   ├── vectara-default.yaml
│   │   ├── mongodb-local.yaml
│   │   └── agentset-prod.yaml
│   ├── query-sets/            # Query collections
│   │   ├── test-queries.txt
│   │   └── production-queries.txt
│   ├── runs/                  # Run results (auto-created)
│   │   ├── <run-id-1>.json
│   │   └── <run-id-2>.json
│   └── comparisons/           # Comparison results (auto-created)
│       └── <comparison-id>.json
└── legal/                     # Domain: Legal documents
    ├── domain.yaml
    ├── systems/
    └── query-sets/
```

## Configuration

### Domain Configuration

`domains/<domain>/domain.yaml`:

```yaml
name: tafsir
description: Islamic tafsir RAG systems
evaluator:
  model: gpt-4                    # LLM model for evaluation
  temperature: 0.0                # Temperature for evaluation
  prompt_template: |              # Evaluation prompt template
    Compare these RAG results for the query: {query}

    Results:
    {results}

    Determine which system provided better results and explain why.
```

### System Configuration

`domains/<domain>/systems/<system>.yaml`:

**Vectara:**
```yaml
name: vectara-default
tool: vectara
config:
  api_key: ${VECTARA_API_KEY}
  corpus_id: ${VECTARA_CORPUS_ID}
  timeout: 30
```

**MongoDB:**
```yaml
name: mongodb-local
tool: mongodb
config:
  connection_uri: ${MONGODB_URI}
  database: my_db
  collection: documents
  index_name: vector_index
  embedding_model: all-MiniLM-L6-v2  # sentence-transformers model
  timeout: 60
```

**Agentset:**
```yaml
name: agentset-prod
tool: agentset
config:
  api_token: ${AGENTSET_API_TOKEN}
  namespace_id: ${AGENTSET_NAMESPACE_ID}
  rerank: true
  timeout: 60
```

### Query Sets

`domains/<domain>/query-sets/<name>.txt`:

Simple text files with one query per line:

```
What is Islamic inheritance law?
Explain the concept of zakat
What are the five pillars of Islam?
```

## Environment Variables

Create a `.env` file with:

```bash
# Vectara
VECTARA_API_KEY=your_key
VECTARA_CORPUS_ID=your_corpus_id

# MongoDB Atlas
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/

# Agentset
AGENTSET_API_TOKEN=your_token
AGENTSET_NAMESPACE_ID=your_namespace_id

# LLM Providers (for evaluation via LiteLLM)
OPENAI_API_KEY=your_key          # For GPT models
ANTHROPIC_API_KEY=your_key       # For Claude models
GEMINI_API_KEY=your_key          # For Gemini models
```

## Supported RAG Systems

RAGDiff v2.0 supports the following RAG systems:

- **Vectara**: Enterprise RAG platform with built-in neural search
- **MongoDB Atlas**: Vector search with MongoDB Atlas and sentence-transformers
- **Agentset**: RAG-as-a-Service platform

### Adding New Systems

1. Create system implementation in `src/ragdiff/systems/`:

```python
from ..core.models_v2 import RetrievedChunk
from ..core.errors import ConfigError, RunError
from .abc import System

class MySystem(System):
    def __init__(self, config: dict):
        super().__init__(config)
        if "api_key" not in config:
            raise ConfigError("Missing required field: api_key")
        self.api_key = config["api_key"]

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Implement search logic
        results = self._call_api(query, top_k)
        return [
            RetrievedChunk(
                content=r["text"],
                score=r["score"],
                metadata={"source": r["source"]}
            )
            for r in results
        ]

# Register the system
from .registry import register_tool
register_tool("mysystem", MySystem)
```

2. Import in `src/ragdiff/systems/__init__.py`:
```python
from . import mysystem  # noqa: F401
```

3. Add tests in `tests/test_systems.py`

## Example Workflows

### A/B Testing Different System Configurations

```bash
# Create two MongoDB variants with different embedding models
cat > domains/ml/systems/mongodb-minilm.yaml <<EOF
name: mongodb-minilm
tool: mongodb
config:
  connection_uri: \${MONGODB_URI}
  database: ml_docs
  collection: articles
  index_name: vector_index
  embedding_model: all-MiniLM-L6-v2
EOF

cat > domains/ml/systems/mongodb-mpnet.yaml <<EOF
name: mongodb-mpnet
tool: mongodb
config:
  connection_uri: \${MONGODB_URI}
  database: ml_docs
  collection: articles
  index_name: vector_index
  embedding_model: all-mpnet-base-v2
EOF

# Run both systems
uv run ragdiff run ml mongodb-minilm test-queries
uv run ragdiff run ml mongodb-mpnet test-queries

# Compare results
uv run ragdiff compare ml <run-id-1> <run-id-2> --format markdown --output ab-test-results.md
```

### Systematic RAG System Development

```bash
# 1. Create baseline run
uv run ragdiff run legal vectara-baseline prod-queries

# 2. Make improvements to your RAG system
# (update embeddings, indexing, etc.)

# 3. Create new run with improved system
uv run ragdiff run legal vectara-improved prod-queries

# 4. Compare baseline vs improved
uv run ragdiff compare legal <baseline-id> <improved-id> --format markdown --output improvements.md

# 5. If improved system is better, make it the new baseline
cp domains/legal/systems/vectara-improved.yaml domains/legal/systems/vectara-baseline.yaml
```

### Multi-System Comparison

```bash
# Run same query set across all systems
uv run ragdiff run tafsir vectara-default test-queries
uv run ragdiff run tafsir mongodb-local test-queries
uv run ragdiff run tafsir agentset-prod test-queries

# Compare all three
uv run ragdiff compare tafsir <vectara-id> <mongodb-id> <agentset-id> \
  --format markdown \
  --output three-way-comparison.md
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run v2.0 tests only
uv run pytest tests/test_core_v2.py tests/test_systems.py tests/test_execution.py tests/test_cli_v2.py

# Run with coverage
uv run pytest tests/ --cov=src

# Run with verbose output
uv run pytest tests/ -v
```

### Code Quality

The project uses pre-commit hooks:
- `ruff` for linting and formatting
- `pytest` for testing
- Whitespace and YAML validation

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Project Structure

```
ragdiff/
├── src/ragdiff/              # Main package
│   ├── cli.py                # Main CLI entry point
│   ├── cli_v2.py             # v2.0 CLI implementation
│   ├── core/                 # Core v2.0 models
│   │   ├── models_v2.py      # Domain-based models
│   │   ├── loaders.py        # File loading utilities
│   │   ├── storage.py        # Persistence utilities
│   │   └── errors.py         # Custom exceptions
│   ├── systems/              # System implementations
│   │   ├── abc.py            # System abstract base class
│   │   ├── registry.py       # System registration
│   │   ├── vectara.py        # Vectara system
│   │   ├── mongodb.py        # MongoDB system
│   │   └── agentset.py       # Agentset system
│   ├── execution/            # Run execution engine
│   └── comparison/           # Comparison engine
├── tests/                    # Test suite (78 v2.0 tests)
├── domains/                  # Domain workspaces
└── pyproject.toml            # Package configuration
```

## Architecture

RAGDiff v2.0 follows the SPIDER protocol for systematic development:

- **Specification**: Clear goals documented in codev/specs/
- **Planning**: Phased implementation (6 phases)
- **Implementation**: Clean domain-based architecture
- **Defense**: Comprehensive test coverage (78 v2.0 tests)
- **Evaluation**: Code reviews and validation
- **Reflection**: Architecture documentation

### Key Design Principles

1. **Domain-Driven**: Organize work around problem domains
2. **Reproducibility**: Snapshot configs and queries in runs
3. **Fail Fast**: Clear error messages, no silent failures
4. **Type Safety**: Pydantic models with validation
5. **Testability**: Every feature has tests
6. **Separation of Concerns**: Clean module boundaries

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Follow existing code style (ruff formatting)
2. Add tests for new features
3. Update documentation
4. Ensure all tests pass

## Acknowledgments

Built following the SPIDER protocol for systematic development.

Supported RAG platforms: Vectara, MongoDB Atlas, Agentset
