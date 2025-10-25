# RAGDiff - Claude Code Instructions

This file contains project-specific instructions for Claude Code when working on the RAGDiff codebase.

## Project Overview

RAGDiff is a flexible framework for comparing Retrieval-Augmented Generation (RAG) systems side-by-side with LLM evaluation support. It provides both a CLI tool and a Python library API.

## Running the CLI

**IMPORTANT**: The package must be installed in editable mode to work properly.

```bash
# Install in editable mode (do this once after cloning)
uv pip install -e .

# Run CLI commands
uv run ragdiff query "your query" --tool vectara --config configs/tafsir.yaml
uv run ragdiff batch inputs/tafsir-test-queries.txt --config configs/tafsir.yaml --output-dir results/
uv run ragdiff compare results/ --output evaluation.jsonl
uv run ragdiff list-tools
uv run ragdiff validate-config
```

**DO NOT** use the old hacky method with `sys.path.insert(0, 'src')` - the package is properly configured in `pyproject.toml` with the correct entry points.

### CLI Command Structure

RAGDiff has three main commands designed to separate expensive RAG queries from cheap LLM evaluation:

#### 1. `query` - Interactive Queries
Query one or more RAG systems interactively.

```bash
# Query a single tool
uv run ragdiff query "What is Islamic inheritance law?" --tool vectara --top-k 10

# Compare multiple tools live
uv run ragdiff query "Your query" --tool vectara --tool agentset --evaluate

# Save results to file
uv run ragdiff query "Your query" --tool vectara --output results.json --format json
```

#### 2. `batch` - Batch Processing
Process multiple queries and save results separately per adapter. This is the expensive step.

```bash
# Basic batch processing - saves per-adapter files
uv run ragdiff batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --output-dir results/ \
  --top-k 10

# This creates: results/vectara.jsonl, results/agentset.jsonl, etc.
```

#### 3. `compare` - Evaluate Saved Results
Load previously saved results and compare them using LLM evaluation. This is the cheap step you can run multiple times.

```bash
# Evaluate saved results
uv run ragdiff compare results/ --output evaluation.jsonl

# Generate markdown report
uv run ragdiff compare results/ --format markdown --output report.md
```

**Why this separation?**
- **Cost savings**: RAG APIs called once, LLM evaluation can be re-run many times
- **Speed**: Evaluation takes seconds vs minutes for RAG queries
- **Experimentation**: Try different evaluation approaches without waiting

## Project Structure

```
ragdiff/
├── src/ragdiff/          # Main package (note: src/ragdiff not just src/)
│   ├── __init__.py       # Public API exports
│   ├── api.py            # Library interface functions
│   ├── cli.py            # Typer CLI implementation
│   ├── version.py        # Version info
│   ├── core/             # Core models and configuration
│   │   ├── models.py     # Data models (RagResult, ComparisonResult, etc.)
│   │   ├── config.py     # Configuration management
│   │   ├── errors.py     # Custom exceptions
│   │   └── serialization.py  # JSON/dict conversion
│   ├── adapters/         # RAG tool adapters
│   │   ├── abc.py        # Abstract base class RagAdapter
│   │   ├── registry.py   # Adapter registration system
│   │   ├── factory.py    # Adapter factory
│   │   ├── vectara.py    # Vectara adapter
│   │   ├── goodmem.py    # Goodmem adapter
│   │   └── agentset.py   # Agentset adapter
│   ├── comparison/       # Comparison engine
│   │   └── engine.py     # Parallel/sequential search execution
│   ├── evaluation/       # LLM evaluation
│   │   └── evaluator.py  # Claude-based evaluation
│   └── display/          # Output formatting
│       └── formatter.py  # Multiple output format support
├── tests/                # Test suite
│   ├── test_core_components.py  # Core functionality tests
│   ├── test_adapters.py         # Adapter tests
│   ├── test_public_api.py       # Library API tests
│   └── test_cli.py              # CLI tests
├── configs/              # Configuration files
│   ├── tafsir.yaml       # Tafsir comparison config
│   └── mawsuah.yaml      # Mawsuah comparison config
├── inputs/               # Input query files
│   └── tafsir-test-queries.txt
└── pyproject.toml        # Package configuration
```

## Architecture

### Adapter Pattern

All RAG tools implement the `RagAdapter` abstract base class:

```python
class RagAdapter(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Execute search and return normalized results."""
        pass
```

New adapters are automatically registered via:
```python
from .registry import register_adapter
register_adapter(MyAdapter)
```

### Configuration System

- YAML-based configuration in `configs/`
- Environment variable substitution with `${VAR_NAME}`
- Multi-tenant credential support (can override credentials per-adapter)
- Adapter variants (same adapter, different config names)

### Version Management

Version is defined in `src/ragdiff/version.py`:
```python
__version__ = "1.1.1"  # Current version
ADAPTER_API_VERSION = "1.0.0"
```

Follow semantic versioning:
- MAJOR: Breaking changes to public API or adapter interface
- MINOR: New features, backward compatible
- PATCH: Bug fixes

## Testing

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_cli.py

# Run with coverage
uv run pytest tests/ --cov=src

# Run with verbose output
uv run pytest tests/ -v
```

All tests must pass before committing. Current test count: 245 tests.

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

### Adding a New Adapter

1. Create `src/ragdiff/adapters/mytool.py`:
```python
from ..core.models import RagResult, ToolConfig
from .abc import RagAdapter

class MyToolAdapter(RagAdapter):
    ADAPTER_API_VERSION = "1.0.0"
    ADAPTER_NAME = "mytool"

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        # Implement search logic
        pass

# Register at module bottom
from .registry import register_adapter
register_adapter(MyToolAdapter)
```

2. Import in `src/ragdiff/adapters/__init__.py`:
```python
from . import mytool  # noqa: F401
```

3. Add config in `configs/tools.yaml`:
```yaml
mytool:
  api_key_env: MYTOOL_API_KEY
  timeout: 30
```

4. Add tests in `tests/test_adapters.py`

### Updating Documentation

- **README.md**: User-facing documentation, examples, installation
- **CLAUDE.md** (this file): Claude Code instructions
- **codev/resources/arch.md**: Architecture documentation (auto-generated)

### Running Comparisons

```bash
# Interactive query (single tool)
uv run ragdiff query "your query" --tool vectara --config configs/tafsir.yaml --top-k 5

# Interactive comparison (multiple tools)
uv run ragdiff query "your query" --tool vectara --tool agentset --evaluate --config configs/tafsir.yaml

# Batch processing workflow
# Step 1: Batch process queries (expensive)
uv run ragdiff batch inputs/tafsir-test-queries.txt \
  --config configs/tafsir.yaml \
  --output-dir results/ \
  --top-k 5

# Step 2: Evaluate results (cheap, can repeat)
uv run ragdiff compare results/ --output evaluation.jsonl
```

## Environment Variables

Required in `.env` file:

```bash
# Vectara
VECTARA_API_KEY=your_key
VECTARA_CORPUS_ID=your_corpus_id

# Goodmem
GOODMEM_API_KEY=your_key

# Agentset
AGENTSET_API_TOKEN=your_token
AGENTSET_NAMESPACE_ID=your_namespace_id

# FAISS (optional - only for OpenAI embeddings)
OPENAI_API_KEY=your_key  # Only needed if using embedding_service: openai

# Anthropic (for LLM evaluation)
ANTHROPIC_API_KEY=your_key
```

## Key Design Principles

1. **Fail Fast**: No fallbacks, clear error messages
2. **Type Safety**: Use Pydantic models, type hints everywhere
3. **Testability**: Every feature has tests
4. **Separation of Concerns**: Clean boundaries between components
5. **Library First**: CLI is thin wrapper around library API

## Common Issues

### "ModuleNotFoundError: No module named 'ragdiff'"

**Fix**: Install package in editable mode
```bash
uv pip install -e .
```

### "command not found: ragdiff"

**Fix**: Use `uv run ragdiff` (not just `ragdiff`)

### Pre-commit hook failures

**Fix**: Hooks auto-fix most issues. If tests fail, fix the code and try again.

### Version mismatch in tests

**Fix**: Update version in both:
- `src/ragdiff/version.py`
- `tests/test_public_api.py` (version assertion)

## SPIDER Protocol

This project follows the SPIDER protocol for systematic development:

- **Specification**: Clear goals documented in codev/specs/
- **Planning**: Implementation plans in codev/plans/
- **Implementation**: Phased development with clear milestones
- **Defense**: Comprehensive test coverage (236 tests)
- **Evaluation**: Code reviews in codev/reviews/
- **Reflection**: Architecture documentation in codev/resources/arch.md

## Notes for Claude Code

- The CLI entry point is `ragdiff` (defined in `pyproject.toml`)
- Always use `uv run ragdiff` for CLI commands
- Source code is in `src/ragdiff/` (note the nested structure)
- When reading imports, remember the package name is `ragdiff` not `src`
- Tests are comprehensive - run them after any changes
- Pre-commit hooks enforce code quality - let them do their job
