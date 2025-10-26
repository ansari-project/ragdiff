# RAGDiff Examples

This directory contains example configurations and scripts demonstrating how to use RAGDiff v2.0 for comparing RAG systems.

## Available Examples

### squad-demo

A complete example using the SQuAD v2.0 dataset to compare two FAISS-based RAG providers with different distance metrics:

- **faiss-l2**: Uses L2 (Euclidean) distance
- **faiss-ip**: Uses Inner Product (cosine similarity with normalized vectors)

This example demonstrates:
- Setting up FAISS indices with different distance metrics
- Creating query sets (both referenced and reference-free)
- Running comparisons between providers
- Analyzing performance differences

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

1. Create a domain directory with the standard structure:
   ```
   examples/my-example/
   ├── domain.yaml           # Domain configuration
   ├── providers/            # Provider configurations
   ├── query-sets/           # Query collections
   ├── scripts/              # Setup and utility scripts
   └── data/                 # Data files (created by scripts)
   ```

2. Add provider configurations in `providers/*.yaml`

3. Create query sets in `query-sets/*.txt`

4. Add setup scripts in `scripts/` to prepare data

5. Document your example in a README.md

See the [RAGDiff documentation](../CLAUDE.md) for more details on the domain-based architecture.
