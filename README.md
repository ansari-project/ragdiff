# RAG Tool Comparison Harness

A flexible framework for comparing Retrieval-Augmented Generation (RAG) tools side-by-side, with support for subjective quality evaluation using LLMs.

## Features

- **Multi-tool Support**: Compare multiple RAG tools in parallel
- **Flexible Adapters**: Easy-to-extend adapter pattern for adding new tools
- **Multiple Output Formats**: Display, JSON, Markdown, and summary formats
- **Performance Metrics**: Automatic latency measurement and result statistics
- **LLM Evaluation**: Support for subjective quality assessment using Claude 4.1 Opus
- **Rich CLI**: Beautiful terminal output with tables and panels
- **Comprehensive Testing**: 90+ tests ensuring reliability

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd tool2

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Create a `configs/tools.yaml` file:

```yaml
tools:
  mawsuah:
    api_key_env: VECTARA_API_KEY
    customer_id: ${VECTARA_CUSTOMER_ID}
    corpus_id: ${VECTARA_CORPUS_ID}
    base_url: https://api.vectara.io
    timeout: 30

  goodmem:
    api_key_env: GOODMEM_API_KEY
    base_url: https://api.goodmem.ai
    timeout: 30

llm:
  model: claude-opus-4-1-20250805
  api_key_env: ANTHROPIC_API_KEY
```

## Usage

### Basic Comparison

```bash
# Compare all configured tools
python -m src compare "What is Islamic inheritance law?"

# Compare specific tools
python -m src compare "Your query" --tool mawsuah --tool goodmem

# Adjust number of results
python -m src compare "Your query" --top-k 10
```

### Output Formats

```bash
# Default display format (side-by-side)
python -m src compare "Your query"

# JSON output
python -m src compare "Your query" --format json

# Markdown output
python -m src compare "Your query" --format markdown

# Summary output
python -m src compare "Your query" --format summary

# Save to file
python -m src compare "Your query" --output results.json --format json
```

### Other Commands

```bash
# List available tools
python -m src list-tools

# Validate configuration
python -m src validate-config

# Run quick test
python -m src quick-test

# Get help
python -m src --help
python -m src compare --help
```

## Project Structure

```
tool2/
├── src/
│   ├── core/           # Core models and configuration
│   │   ├── models.py    # Data models (RagResult, ComparisonResult, etc.)
│   │   └── config.py    # Configuration management
│   ├── adapters/        # Tool adapters
│   │   ├── base.py      # Base adapter implementing SearchVectara interface
│   │   ├── mawsuah.py   # Vectara/Mawsuah adapter
│   │   ├── goodmem.py   # Goodmem adapter with mock fallback
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
- **Adapters**: Tool-specific implementations (Mawsuah, Goodmem)
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
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_cli.py

# Run with coverage
python -m pytest tests/ --cov=src
```

### Code Style

The project uses:
- Black for formatting
- Ruff for linting
- MyPy for type checking

## Environment Variables

Required environment variables:

- `VECTARA_API_KEY`: For Mawsuah/Vectara access
- `VECTARA_CUSTOMER_ID`: Vectara customer ID
- `VECTARA_CORPUS_ID`: Vectara corpus ID
- `GOODMEM_API_KEY`: For Goodmem access (optional, uses mock if not set)
- `ANTHROPIC_API_KEY`: For LLM evaluation (optional)

## License

[Your License]

## Contributing

Contributions welcome! Please follow the existing code style and add tests for new features.

## Acknowledgments

Built following the SPIDER protocol for systematic development.