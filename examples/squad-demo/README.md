# SQuAD FAISS Demo

This example demonstrates RAGDiff v2.0 using the SQuAD v2.0 dataset with two FAISS providers that differ in their embedding models.

## Overview

This example compares two FAISS-based RAG systems using **different embedding models** to demonstrate quality differences:

1. **faiss-small**: `paraphrase-MiniLM-L3-v2`
   - 17MB model, 3 layers, 384 dimensions
   - Fast but less accurate
   - Good for high-throughput scenarios

2. **faiss-large**: `all-MiniLM-L12-v2`
   - 120MB model, 12 layers, 384 dimensions
   - Slower but more accurate
   - Better semantic understanding

Both use **L2 (Euclidean) distance** for fair comparison - the quality difference comes purely from the embedding model, not the distance metric.

## Dataset

- **Source**: SQuAD v2.0 (Stanford Question Answering Dataset)
- **Documents**: ~1,200 unique context paragraphs from Wikipedia
- **Query Sets**: 100 test queries

## Setup

### Prerequisites

Install required dependencies:

```bash
# Core dependencies (if not already installed from project root)
cd /path/to/ragdiff
uv venv
uv pip install -e .

# Install example dependencies
cd examples/squad-demo
uv pip install -e .
```

### Build Indices

Execute the setup steps:

```bash
cd examples/squad-demo

# Step 1: Download and prepare dataset
uv run python scripts/setup_dataset.py

# Step 2: Build small model index
uv run python scripts/build_faiss_small.py

# Step 3: Build large model index
uv run python scripts/build_faiss_large.py

# Step 4: Generate query sets
uv run python scripts/generate_queries.py
```

**What this does:**
1. Download SQuAD v2.0 dataset from HuggingFace
2. Extract unique context paragraphs as documents
3. Generate embeddings using sentence-transformers
4. Build two FAISS indices (small and large models, both with L2 distance)
5. Create query sets

## Usage

You can use RAGDiff either via the **command-line interface (CLI)** or the **Python API**.

### Python API (Jupyter Notebook)

For an interactive tutorial using the Python API, see **[squad_demo_api.ipynb](squad_demo_api.ipynb)**.

The notebook demonstrates:
- Loading domain, provider, and query set configurations programmatically
- Executing query sets against providers with `execute_run()`
- Comparing runs using LLM evaluation with `compare_runs()`
- Analyzing results and exporting to JSON/Markdown
- Accessing historical run data

This is the recommended approach if you want to:
- Integrate RAGDiff into your Python applications
- Customize the evaluation workflow
- Build custom analysis and visualization tools
- Automate RAG system comparisons

### CLI Usage

The following sections show how to use RAGDiff from the command line.

#### Run Queries

Execute query sets against each provider:

```bash
# Back to project root
cd ../..

# Run against small model
uv run ragdiff run --domain-dir examples/squad-demo/domains/squad --provider faiss-small --query-set test-queries

# Run against large model
uv run ragdiff run --domain-dir examples/squad-demo/domains/squad --provider faiss-large --query-set test-queries

# Short form with flags
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-large -q test-queries
```

#### Compare Results

After running queries, compare the results:

```bash
# Compare two runs (replace with actual run labels/IDs from output)
uv run ragdiff compare --domain-dir examples/squad-demo/domains/squad --run <run-label-1> --run <run-label-2>

# Short form
uv run ragdiff compare -d examples/squad-demo/domains/squad -r <run-label-1> -r <run-label-2>

# Export to JSON
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r <run-label-1> -r <run-label-2> \
  --format json \
  --output comparison.json

# Export to Markdown report
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r <run-label-1> -r <run-label-2> \
  --format markdown \
  --output comparison-report.md

# Auto-compare latest runs for each provider
uv run ragdiff compare -d examples/squad-demo/domains/squad
```

## Expected Results

The larger embedding model (12 layers) should show:
- **Better retrieval accuracy** (higher quality scores)
- **More wins** vs the small model
- **Slower query times** (due to larger model inference)

The comparison report will show:
- Win/loss statistics
- Quality score differences
- Latency comparison (avg, median, min, max)
- Number of chunks returned per query
- Representative examples of where each model excels

## Directory Structure

```
squad-demo/
├── README.md                           # This file
├── squad_demo_api.ipynb                # Python API tutorial (Jupyter notebook)
├── pyproject.toml                      # Python dependencies
├── domains/                            # Domain configurations
│   └── squad/                          # The "squad" domain
│       ├── domain.yaml                 # Domain configuration
│       ├── providers/                  # Provider configs
│       │   ├── faiss-small.yaml        # Small model config
│       │   └── faiss-large.yaml        # Large model config
│       ├── query-sets/                 # Query files
│       │   └── test-queries.txt        # 100 test questions
│       ├── runs/                       # Run results (auto-created)
│       └── comparisons/                # Comparison results (auto-created)
├── data/                               # Shared data files (generated)
│   ├── documents.jsonl                 # Document corpus
│   ├── squad_raw.json                  # Raw SQuAD data
│   ├── faiss_small.index               # Small model FAISS index
│   └── faiss_large.index               # Large model FAISS index
└── scripts/                            # Setup scripts
    ├── setup_all.sh                    # Master setup script
    ├── setup_dataset.py                # Download and prepare SQuAD
    ├── build_faiss_small.py            # Build small model index
    ├── build_faiss_large.py            # Build large model index
    ├── generate_queries.py             # Generate query sets
    └── test_setup.py                   # Verify setup
```

## Rebuilding Indices

If you want to rebuild the indices with different models:

1. **Enter the demo environment:**
   ```bash
   cd examples/squad-demo
   source .venv/bin/activate  # or use: uv run python
   ```

2. **Build the small model index:**
   ```bash
   uv run python scripts/build_faiss_small.py
   ```
   This creates `data/faiss_small.index` using paraphrase-MiniLM-L3-v2 with L2 distance

3. **Build the large model index:**
   ```bash
   uv run python scripts/build_faiss_large.py
   ```
   This creates `data/faiss_large.index` using all-MiniLM-L12-v2 with L2 distance

4. **Run queries against both providers:**
   ```bash
   cd ../..  # Back to project root
   uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries
   uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-large -q test-queries
   ```

5. **Compare the results:**
   ```bash
   uv run ragdiff compare -d examples/squad-demo/domains/squad \
     -r <run-label-1> -r <run-label-2> \
     --format markdown \
     --output examples/squad-demo/comparison-report.md
   ```

## Advanced Usage

### Adjust Concurrency

Speed up query execution with parallel requests:

```bash
uv run ragdiff run -d examples/squad-demo/domains/squad \
  -p faiss-small -q test-queries \
  --concurrency 10
```

### Use Different Embedding Models

Modify the provider configs to use different embedding models:

```yaml
config:
  embedding_service: sentence-transformers
  embedding_model: all-mpnet-base-v2  # Higher quality, 768 dims
```

Then rebuild the indices with the new model.

### Custom Query Sets

Create your own query set:

```bash
# Create a new query file
cat > examples/squad-demo/domains/squad/query-sets/custom-queries.txt <<EOF
What is machine learning?
How does neural network training work?
What are transformers in NLP?
EOF

# Run with custom queries
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q custom-queries
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'datasets'"

Install required dependencies:
```bash
cd examples/squad-demo
uv pip install -e .
```

### "FAISS index not found"

Run the setup scripts:
```bash
cd examples/squad-demo
./scripts/setup_all.sh
```

### "Documents file not found"

Ensure you've run `setup_dataset.py` before building indices.

### Slow index building

This is normal for the first run:
- Downloading the SQuAD dataset takes a few minutes
- Generating embeddings for ~1,200 documents takes 1-2 minutes
- Building indices is very fast (<1 second)

## Learning More

- [RAGDiff Documentation](../../CLAUDE.md)
- [FAISS Documentation](https://github.com/facebookresearch/faiss/wiki)
- [SQuAD Dataset](https://rajpurkar.github.io/SQuAD-explorer/)
- [Sentence Transformers](https://www.sbert.net/)

## Model Characteristics

### Small Model (paraphrase-MiniLM-L3-v2)
- **Size**: 17MB
- **Layers**: 3
- **Dimensions**: 384
- **Speed**: Fast
- **Quality**: Good for basic similarity

### Large Model (all-MiniLM-L12-v2)
- **Size**: 120MB
- **Layers**: 12
- **Dimensions**: 384
- **Speed**: Slower (~72% slower on average)
- **Quality**: Better semantic understanding

The comparison demonstrates the classic **quality vs speed tradeoff** in embedding models!
