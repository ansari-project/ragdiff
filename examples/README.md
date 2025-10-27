# RAGDiff Examples

This directory contains example configurations and scripts demonstrating how to use RAGDiff v2.0 for comparing RAG systems.

## Available Examples

### squad-demo

A complete example using the SQuAD v2.0 dataset to compare three RAG providers with different approaches:

- **faiss-small**: FAISS with small embedding model (paraphrase-MiniLM-L3-v2)
- **faiss-large**: FAISS with large embedding model (all-MiniLM-L12-v2)
- **bm25-keyword**: BM25 keyword-based retrieval baseline

This example demonstrates:
- Setting up FAISS indices with different embedding models
- BM25 keyword-based retrieval as a baseline
- Creating query sets with and without reference answers
- **Head-to-head comparison**: LLM-based evaluation between providers
- **Reference-based evaluation**: Objective scoring against ground-truth answers
- Three-way comparisons and performance analysis

See [squad-demo/README.md](squad-demo/README.md) for detailed instructions.

## Quick Start

```bash
# Navigate to an example directory
cd examples/squad-demo

# Run the setup script
./scripts/setup_all.sh

# Run comparisons (see example-specific README for details)
```

## Creating Your Own Examples

To create a new example:

1. Create a domain directory with the standard v2.0 structure:
   ```
   examples/my-example/
   ├── README.md                     # Example documentation
   ├── pyproject.toml                # Python dependencies (if needed)
   ├── domains/                      # Domain configurations
   │   └── my-domain/                # Your domain
   │       ├── domain.yaml           # Domain config (evaluator settings)
   │       ├── providers/            # Provider configurations
   │       │   ├── provider1.yaml
   │       │   └── provider2.yaml
   │       ├── query-sets/           # Query collections
   │       │   └── test-queries.txt
   │       ├── runs/                 # Run results (auto-created)
   │       └── comparisons/          # Comparison results (auto-created)
   ├── data/                         # Data files (created by scripts)
   └── scripts/                      # Setup and utility scripts
   ```

2. Configure your domain in `domains/my-domain/domain.yaml`:
   ```yaml
   name: my-domain
   description: Description of your domain
   evaluator:
     model: gpt-4  # LLM model for evaluation
     temperature: 0.0
     prompt_template: |
       Compare these RAG results...
   ```

3. Add provider configurations in `domains/my-domain/providers/*.yaml`

4. Create query sets in `domains/my-domain/query-sets/*.txt`

5. Add setup scripts in `scripts/` to prepare data and indices

6. Document your example in a README.md

See the [RAGDiff documentation](../CLAUDE.md) for more details on the domain-based architecture.
