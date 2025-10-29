# SQuAD RAG Comparison Demo

This example demonstrates RAGDiff v2.0 using the SQuAD v2.0 dataset with three RAG providers, showcasing both **head-to-head comparison** and **reference-based evaluation**.

## Overview

This example compares three RAG systems to demonstrate different approaches and quality tradeoffs:

1. **faiss-small**: `paraphrase-MiniLM-L3-v2`
   - 17MB model, 3 layers, 384 dimensions
   - Fast but less accurate
   - Good for high-throughput scenarios

2. **faiss-large**: `all-MiniLM-L12-v2`
   - 120MB model, 12 layers, 384 dimensions
   - Slower but more accurate
   - Better semantic understanding

3. **bm25-keyword**: BM25 keyword-based retrieval
   - Pure keyword matching baseline
   - No embeddings required
   - Fast, deterministic results
   - Useful for establishing performance baselines

The FAISS providers use **L2 (Euclidean) distance** for fair comparison - the quality difference comes purely from the embedding model, not the distance metric.

## Dataset

- **Source**: SQuAD v2.0 (Stanford Question Answering Dataset)
- **Documents**: ~1,200 unique context paragraphs from Wikipedia
- **Query Sets**: 100 test queries
- **Reference Answers**: Ground-truth answers from SQuAD for objective evaluation

## Evaluation Modes

This demo supports two evaluation modes:

### 1. Head-to-Head Comparison
- LLM-based evaluation comparing multiple providers
- Qualitative assessment of which provider performed better
- Useful when no ground truth exists
- Example: `faiss-small` vs `faiss-large` comparison

### 2. Reference-Based Evaluation
- Objective scoring against ground-truth SQuAD answers
- Quantitative correctness assessment (0-100 score)
- Automatic detection when reference answers are present
- Example: Evaluating `bm25-keyword` accuracy against SQuAD references

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

# Step 5: Generate reference queries (with ground-truth answers)
uv run python scripts/generate_reference_queries.py
```

**What this does:**
1. Download SQuAD v2.0 dataset from HuggingFace
2. Extract unique context paragraphs as documents
3. Generate embeddings using sentence-transformers
4. Build two FAISS indices (small and large models, both with L2 distance)
5. Create query sets (standard queries)
6. Create reference query sets with ground-truth answers for objective evaluation

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
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries

# Run against large model
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-large -q test-queries

# Run against BM25 baseline
uv run ragdiff run -d examples/squad-demo/domains/squad -p bm25-keyword -q test-queries

# With concurrency for faster execution
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries --concurrency 20
```

#### Compare Results

RAGDiff automatically detects whether to use head-to-head comparison or reference-based evaluation based on whether reference answers are present.

#### Head-to-Head Comparison (No References)

Compare two providers using LLM evaluation:

```bash
# Compare two runs (replace with actual run labels/IDs from output)
uv run ragdiff compare -d examples/squad-demo/domains/squad -r <run-label-1> -r <run-label-2>

# Three-way comparison
uv run ragdiff compare -d examples/squad-demo/domains/squad -r faiss-small-001 -r faiss-large-001 -r bm25-keyword-001

# Export to Markdown report
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r <run-label-1> -r <run-label-2> \
  --format markdown \
  --output comparison-report.md

# Auto-compare latest runs for each provider
uv run ragdiff compare -d examples/squad-demo/domains/squad
```

#### Reference-Based Evaluation (With Ground Truth)

When runs include reference answers, RAGDiff performs objective correctness evaluation:

```bash
# Single run evaluation against references
uv run ragdiff compare -d examples/squad-demo/domains/squad -r <run-with-references>

# Compare multiple runs with references (shows which performs better on correctness)
uv run ragdiff compare -d examples/squad-demo/domains/squad -r faiss-small-ref -r bm25-keyword-ref

# Export to JSON
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r <run-label> \
  --format json \
  --output eval-report.json

# Limit evaluation to first 10 queries (faster testing)
uv run ragdiff compare -d examples/squad-demo/domains/squad -r <run-label> --limit 10
```

## Expected Results

**See [example-comparison-report.md](example-comparison-report.md)** for a complete example comparison report showing faiss-small vs faiss-large evaluation results.

### Provider Performance Characteristics

**faiss-large** (12 layers):
- **Better retrieval accuracy** (higher quality scores)
- **More wins** vs faiss-small in head-to-head comparison
- **Slower query times** (~72% slower than small model)
- Better semantic understanding

**faiss-small** (3 layers):
- **Faster queries** (~32ms average)
- Lower quality scores but acceptable for many use cases
- Good for high-throughput scenarios

**bm25-keyword**:
- **Fastest queries** (pure keyword matching)
- Baseline performance for comparison
- No semantic understanding
- Works well for exact keyword matches

### Comparison Reports

The comparison reports will show:

**Head-to-Head Mode:**
- Win/loss statistics per provider
- Quality score differences
- Latency comparison (avg, median, min, max)
- Number of chunks returned per query
- Representative examples of where each provider excels
- Common themes and differentiators

**Example:** See [example-comparison-report.md](example-comparison-report.md) for a complete head-to-head comparison between faiss-small and faiss-large.

**Reference-Based Mode:**
- Correctness scores (0-100) per query
- Average correctness per provider
- Success/failure breakdown
- Detailed reasoning for each evaluation
- Cost and token usage per evaluation

## Directory Structure

```
squad-demo/
├── README.md                           # This file
├── example-comparison-report.md        # Example comparison report
├── squad_demo_api.ipynb                # Python API tutorial (Jupyter notebook)
├── pyproject.toml                      # Python dependencies
├── domains/                            # Domain configurations
│   └── squad/                          # The "squad" domain
│       ├── domain.yaml                 # Domain configuration
│       ├── providers/                  # Provider configs
│       │   ├── faiss-small.yaml        # Small model config
│       │   ├── faiss-large.yaml        # Large model config
│       │   └── bm25-keyword.yaml       # BM25 baseline config
│       ├── query-sets/                 # Query files
│       │   ├── test-queries.txt        # 100 test questions
│       │   └── reference-queries.txt   # Queries with ground-truth answers
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
    ├── generate_reference_queries.py   # Generate queries with references
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

Speed up query execution and evaluation with parallel requests:

```bash
# Faster query execution (default: 10)
uv run ragdiff run -d examples/squad-demo/domains/squad \
  -p faiss-small -q test-queries \
  --concurrency 20

# Faster comparison evaluation (default: 2)
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r run1 -r run2 \
  --concurrency 10
```

### Use Different LLM Models for Evaluation

Override the default evaluation model:

```bash
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r run1 -r run2 \
  --model anthropic/claude-sonnet-4-5 \
  --temperature 0.0
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

### Three-Way Comparisons

Compare all three providers simultaneously:

```bash
# Run all three providers
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-small -q test-queries -l small-001
uv run ragdiff run -d examples/squad-demo/domains/squad -p faiss-large -q test-queries -l large-001
uv run ragdiff run -d examples/squad-demo/domains/squad -p bm25-keyword -q test-queries -l bm25-001

# Compare all three
uv run ragdiff compare -d examples/squad-demo/domains/squad \
  -r small-001 -r large-001 -r bm25-001 \
  --format markdown \
  --output three-way-comparison.md
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

## Provider Characteristics

### faiss-small (paraphrase-MiniLM-L3-v2)
- **Size**: 17MB embedding model
- **Layers**: 3
- **Dimensions**: 384
- **Speed**: Fast (~32ms avg query time)
- **Quality**: Good for basic similarity
- **Use Case**: High-throughput scenarios

### faiss-large (all-MiniLM-L12-v2)
- **Size**: 120MB embedding model
- **Layers**: 12
- **Dimensions**: 384
- **Speed**: Slower (~56ms avg, 72% slower than small)
- **Quality**: Better semantic understanding
- **Use Case**: Quality-focused applications

### bm25-keyword
- **Algorithm**: BM25 (Best Matching 25)
- **Approach**: Pure keyword matching, no embeddings
- **Speed**: Very fast (deterministic, no model inference)
- **Quality**: Good for exact keyword matches, poor for semantic similarity
- **Use Case**: Baseline comparisons, exact-match requirements

## Key Insights

This demo demonstrates:

1. **Quality vs Speed Tradeoff**: Larger embedding models provide better semantic understanding at the cost of latency
2. **Semantic vs Keyword**: Embedding-based approaches (FAISS) vs keyword-based (BM25) retrieval
3. **Evaluation Modes**: Both subjective (head-to-head LLM comparison) and objective (reference-based correctness) evaluation
4. **Reproducibility**: All configurations, queries, and results are version-controlled and reproducible
