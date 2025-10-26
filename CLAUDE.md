# RAGDiff v2.0 - Claude Code Instructions

This file contains project-specific instructions for Claude Code when working on the RAGDiff codebase.

## Project Overview

RAGDiff v2.0 is a domain-based framework for comparing Retrieval-Augmented Generation (RAG) systems with LLM evaluation support. It provides a CLI tool and Python library API for systematic RAG system comparison.

## What's New in v2.0

RAGDiff v2.0 introduces a **domain-based architecture** that organizes RAG comparisons around problem domains:

- **Domains**: Separate workspaces for different problem areas (e.g., tafsir, legal, medical)
- **Systems**: RAG system configurations (e.g., vectara-default, mongodb-local)
- **Query Sets**: Collections of test queries for evaluation
- **Runs**: Executions of query sets against systems
- **Comparisons**: LLM-based evaluations of multiple runs

This architecture replaces the v1.x adapter-based approach with a more structured, reproducible workflow.

## Running the CLI

**IMPORTANT**: The package must be installed in editable mode to work properly.

```bash
# Install in editable mode (do this once after cloning)
uv pip install -e .

# Run v2.0 CLI commands
uv run ragdiff run tafsir vectara-default test-queries
uv run ragdiff compare tafsir <run-id-1> <run-id-2>
```

**DO NOT** use the old hacky method with `sys.path.insert(0, 'src')` - the package is properly configured in `pyproject.toml` with the correct entry points.

### CLI Command Structure

RAGDiff v2.0 has two main commands:

#### 1. `run` - Execute Query Sets

Execute a query set against a system and save results:

```bash
# Basic run
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
- Loads system configuration from `domains/<domain>/systems/<system>.yaml`
- Loads queries from `domains/<domain>/query-sets/<query-set>.txt`
- Executes all queries against the system
- Saves run results to `domains/<domain>/runs/<run-id>.json`
- Shows progress bar and summary table

#### 2. `compare` - Evaluate Runs

Compare multiple runs using LLM evaluation:

```bash
# Basic comparison
uv run ragdiff compare <domain> <run-id-1> <run-id-2> [<run-id-3> ...]

# Examples
uv run ragdiff compare tafsir abc123 def456
uv run ragdiff compare tafsir abc123 def456 --format json --output comparison.json

# With options
uv run ragdiff compare tafsir abc123 def456 \
  --domains-dir ./domains \
  --model gpt-4 \
  --temperature 0.0 \
  --format markdown \
  --output report.md
```

**Output formats:**
- `table`: Rich table to console (default)
- `json`: JSON to file or console
- `markdown`: Markdown report to file or console

**What it does:**
- Loads runs from `domains/<domain>/runs/`
- Uses LLM (via LiteLLM) to evaluate which system performed better
- Saves comparison to `domains/<domain>/comparisons/<comparison-id>.json`
- Outputs results in specified format

### Domain Directory Structure

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

## Project Structure

```
ragdiff/
├── src/ragdiff/              # Main package
│   ├── __init__.py           # Public API exports
│   ├── cli.py                # Main CLI entry point (imports cli_v2)
│   ├── cli_v2.py             # v2.0 CLI implementation
│   ├── version.py            # Version info
│   ├── core/                 # Core v2.0 models
│   │   ├── models_v2.py      # Domain-based models (Run, Comparison, etc.)
│   │   ├── loaders.py        # File loading utilities
│   │   ├── storage.py        # Persistence utilities
│   │   ├── errors.py         # Custom exceptions
│   │   └── logging.py        # Logging configuration
│   ├── systems/              # System implementations
│   │   ├── abc.py            # System abstract base class
│   │   ├── registry.py       # System registration
│   │   ├── factory.py        # System factory
│   │   ├── vectara.py        # Vectara system
│   │   ├── mongodb.py        # MongoDB system
│   │   └── agentset.py       # Agentset system
│   ├── execution/            # Run execution
│   │   └── executor.py       # Parallel query execution
│   ├── comparison/           # Comparison engine
│   │   └── evaluator.py      # LLM-based evaluation
│   └── display/              # Output formatting (v1.x, kept for compatibility)
├── tests/                    # Test suite
│   ├── test_core_v2.py       # Core v2.0 tests
│   ├── test_systems.py       # System tests
│   ├── test_execution.py     # Execution engine tests
│   └── test_cli_v2.py        # CLI tests
├── domains/                  # Domain workspaces
│   └── example-domain/       # Example domain structure
└── pyproject.toml            # Package configuration
```

## Architecture

### Domain-Based Architecture

RAGDiff v2.0 organizes everything around **domains**:

1. **Domain** (`domains/<domain>/domain.yaml`):
   - Name and description
   - Evaluator configuration (LLM model, temperature, prompt template)

2. **System** (`domains/<domain>/systems/<system>.yaml`):
   - Name, tool type (vectara, mongodb, agentset)
   - Configuration (API keys, endpoints, etc.)

3. **Query Set** (`domains/<domain>/query-sets/<name>.txt`):
   - Text file with one query per line
   - Used for consistent evaluation across systems

4. **Run** (`domains/<domain>/runs/<run-id>.json`):
   - Results of executing a query set against a system
   - Includes all query results, errors, timing info
   - Snapshots system config and query set for reproducibility

5. **Comparison** (`domains/<domain>/comparisons/<comparison-id>.json`):
   - LLM evaluation of multiple runs
   - Per-query winner determination
   - Quality scores and analysis

### System Pattern

All RAG systems implement the `System` abstract base class:

```python
class System(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search and return normalized results."""
        pass
```

New systems are automatically registered via:
```python
from .registry import register_tool
register_tool("mongodb", MongoDBSystem)
```

### Configuration System

- **YAML-based** configuration in domain directories
- **Environment variable substitution** with `${VAR_NAME}` (preserved in snapshots)
- **LiteLLM integration** for multi-provider LLM support
- **Config snapshotting** for reproducibility

### Version Management

Version is defined in `src/ragdiff/version.py`:
```python
__version__ = "2.0.0"  # Current version
```

Follow semantic versioning:
- MAJOR: Breaking changes to public API or system interface
- MINOR: New features, backward compatible
- PATCH: Bug fixes

## Testing

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

All v2.0 tests must pass before committing. Current v2.0 test count: 78 tests.

## Code Quality

The project uses pre-commit hooks:
- `ruff` for linting and formatting
- `pytest` for testing
- Whitespace and YAML validation

Pre-commit hooks will automatically:
- Format code with ruff
- Fix linting issues where possible
- Run all tests
- Reject commits if tests fail

## Development Workflow

1. **Make changes** to source code in `src/ragdiff/`
2. **Add tests** in `tests/` for new functionality
3. **Run tests** with `uv run pytest tests/`
4. **Test CLI** with `uv run ragdiff <command>`
5. **Update version** in `src/ragdiff/version.py` if needed
6. **Commit** - pre-commit hooks will validate everything

## Common Tasks

### Creating a New Domain

```bash
# Create domain structure
mkdir -p domains/my-domain/{systems,query-sets,runs,comparisons}

# Create domain.yaml
cat > domains/my-domain/domain.yaml <<EOF
name: my-domain
description: Description of my domain
evaluator:
  model: gpt-4
  temperature: 0.0
  prompt_template: |
    Compare these RAG results...
EOF

# Create a system config
cat > domains/my-domain/systems/vectara-test.yaml <<EOF
name: vectara-test
tool: vectara
config:
  api_key: \${VECTARA_API_KEY}
  corpus_id: \${VECTARA_CORPUS_ID}
  timeout: 30
EOF

# Create a query set
cat > domains/my-domain/query-sets/test-queries.txt <<EOF
Query 1
Query 2
Query 3
EOF
```

### Adding a New System Implementation

1. Create `src/ragdiff/systems/mysystem.py`:
```python
from ..core.models_v2 import RetrievedChunk
from ..core.errors import ConfigError, RunError
from .abc import System

class MySystem(System):
    def __init__(self, config: dict):
        super().__init__(config)
        # Validate config
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

### Running Comparisons

```bash
# Step 1: Run query sets against different systems
uv run ragdiff run tafsir vectara-default test-queries
uv run ragdiff run tafsir mongodb-local test-queries
uv run ragdiff run tafsir agentset-prod test-queries

# Note the run IDs from the output (or check domains/tafsir/runs/)

# Step 2: Compare the runs
uv run ragdiff compare tafsir <run-id-1> <run-id-2> <run-id-3>

# Step 3: Export to different formats
uv run ragdiff compare tafsir <run-id-1> <run-id-2> --format json --output comparison.json
uv run ragdiff compare tafsir <run-id-1> <run-id-2> --format markdown --output report.md
```

## Environment Variables

Required in `.env` file:

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
OPENROUTER_API_KEY=your_key      # For OpenRouter (optional)
```

## Key Design Principles

1. **Domain-Driven**: Organize work around problem domains
2. **Reproducibility**: Snapshot configs and queries in runs
3. **Fail Fast**: No fallbacks, clear error messages
4. **Type Safety**: Pydantic models, type hints everywhere
5. **Testability**: Every feature has tests
6. **Separation of Concerns**: Clean boundaries between components

## Common Issues

### "ModuleNotFoundError: No module named 'ragdiff'"

**Fix**: Install package in editable mode
```bash
uv pip install -e .
```

### "command not found: ragdiff"

**Fix**: Use `uv run ragdiff` (not just `ragdiff`)

### "Domain not found"

**Fix**: Ensure domain directory exists at `domains/<domain>/` with `domain.yaml`

### "System config not found"

**Fix**: Ensure system config exists at `domains/<domain>/systems/<system>.yaml`

### "Query set not found"

**Fix**: Ensure query set exists at `domains/<domain>/query-sets/<query-set>.txt`

### LiteLLM errors

**Fix**: Ensure LiteLLM is installed (`uv pip install litellm`) and API keys are set

## SPIDER Protocol

This project follows the SPIDER protocol for systematic development:

- **Specification**: Clear goals documented in codev/specs/
- **Planning**: Implementation plans in codev/plans/
- **Implementation**: Phased development with clear milestones (6 phases)
- **Defense**: Comprehensive test coverage (78 v2.0 tests)
- **Evaluation**: Code reviews in codev/reviews/
- **Reflection**: Architecture documentation in codev/resources/arch.md

## v2.0 Implementation Status

- ✅ Phase 1: Core data models, file loading, storage (29 tests)
- ✅ Phase 2: System interface, tool registry (29 tests)
- ✅ Phase 3: Run execution engine (12 tests)
- ✅ Phase 4: Comparison engine with LiteLLM (5 tests)
- ✅ Phase 5: CLI commands (8 tests)
- 🔄 Phase 6: Documentation & CI/CD (in progress)

## Notes for Claude Code

- The CLI entry point is `ragdiff` (defined in `pyproject.toml`)
- Always use `uv run ragdiff` for CLI commands
- v2.0 uses domain-based architecture (not adapters)
- Source code is in `src/ragdiff/` (note the nested structure)
- v2.0 models are in `core/models_v2.py`, systems are in `systems/`
- Tests are comprehensive - run them after any changes
- Pre-commit hooks enforce code quality - let them do their job
- v1.x code still exists but is not the primary interface
