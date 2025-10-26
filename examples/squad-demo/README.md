# SQuAD FAISS Demo

This example demonstrates RAGDiff v2.0 using the SQuAD v2.0 dataset with two FAISS providers that differ in their distance metrics.

## Overview

This example compares two FAISS-based RAG systems:

1. **faiss-l2**: Uses L2 (Euclidean) distance
   - Measures straight-line distance between vectors
   - Sensitive to vector magnitude
   - Smaller distances = higher similarity
   - Range: [0, ∞)

2. **faiss-ip**: Uses Inner Product (cosine similarity)
   - Measures dot product between normalized vectors
   - Equivalent to cosine similarity when vectors are normalized
   - Higher scores = higher similarity
   - Range: [-1, 1] for normalized vectors

## Dataset

- **Source**: SQuAD v2.0 (Stanford Question Answering Dataset)
- **Documents**: ~1,200 unique context paragraphs from Wikipedia
- **Embeddings**: Generated using `all-MiniLM-L6-v2` (384 dimensions)
- **Query Sets**:
  - **referenced-queries.txt**: 100 questions with ground truth answers
  - **reference-free-queries.txt**: 100 questions without answers

## Setup

### Prerequisites

Install required dependencies:

```bash
# Core dependencies (if not already installed)
uv pip install -e .

# Additional dependencies for this example
uv pip install datasets sentence-transformers faiss-cpu numpy
```

### Run Setup

Execute the master setup script:

```bash
cd examples/squad-demo
./scripts/setup_all.sh
```

This will:
1. Download SQuAD v2.0 dataset from HuggingFace
2. Extract unique context paragraphs as documents
3. Generate embeddings using sentence-transformers
4. Build two FAISS indices (L2 and Inner Product)
5. Create query sets

### Manual Setup (Optional)

You can also run each step individually:

```bash
cd examples/squad-demo/scripts

# Step 1: Download and prepare dataset
python3 setup_dataset.py

# Step 2: Build L2 index
python3 build_faiss_l2.py

# Step 3: Build Inner Product index
python3 build_faiss_ip.py

# Step 4: Generate query sets
python3 generate_queries.py
```

## Usage

### Run Queries

Execute query sets against each provider:

```bash
# Run against L2 index
uv run ragdiff run squad-demo faiss-l2 referenced-queries --domains-dir examples

# Run against Inner Product index
uv run ragdiff run squad-demo faiss-ip referenced-queries --domains-dir examples

# Or use reference-free queries
uv run ragdiff run squad-demo faiss-l2 reference-free-queries --domains-dir examples
uv run ragdiff run squad-demo faiss-ip reference-free-queries --domains-dir examples
```

### Compare Results

After running queries, compare the results:

```bash
# Compare two runs (replace with actual run IDs from output)
uv run ragdiff compare squad-demo <run-id-1> <run-id-2> --domains-dir examples

# Export to JSON
uv run ragdiff compare squad-demo <run-id-1> <run-id-2> \
  --domains-dir examples \
  --format json \
  --output comparison.json

# Export to Markdown report
uv run ragdiff compare squad-demo <run-id-1> <run-id-2> \
  --domains-dir examples \
  --format markdown \
  --output report.md
```

## Expected Results

The two distance metrics often produce similar but not identical results:

- **L2 distance** is sensitive to vector magnitude and absolute differences
- **Inner Product** (cosine similarity) focuses on vector direction/angle

You may observe:
- Similar top-ranked documents for most queries
- Different ranking orders, especially for documents with varying text lengths
- Potential performance differences on specific query types

## Directory Structure

```
squad-demo/
├── README.md                           # This file
├── domain.yaml                         # Domain configuration
├── providers/                          # Provider configs
│   ├── faiss-l2.yaml                   # L2 distance config
│   └── faiss-ip.yaml                   # Inner Product config
├── query-sets/                         # Query files (generated)
│   ├── referenced-queries.txt          # 100 questions with ground truth
│   └── reference-free-queries.txt      # 100 questions without answers
├── scripts/                            # Setup scripts
│   ├── setup_all.sh                    # Master setup script
│   ├── setup_dataset.py                # Download and prepare SQuAD
│   ├── build_faiss_l2.py               # Build L2 index
│   ├── build_faiss_ip.py               # Build Inner Product index
│   └── generate_queries.py             # Generate query sets
├── data/                               # Data files (generated)
│   ├── documents.jsonl                 # Document corpus
│   ├── squad_raw.json                  # Raw SQuAD data
│   ├── faiss_l2.index                  # L2 FAISS index
│   ├── faiss_ip.index                  # Inner Product FAISS index
│   └── referenced-queries-metadata.json # Ground truth answers
├── runs/                               # Run results (auto-created)
└── comparisons/                        # Comparison results (auto-created)
```

## Query Set Details

### Referenced Queries

- **Count**: 100 questions
- **Source**: SQuAD v2.0 validation split
- **Ground Truth**: Answers available in `data/referenced-queries-metadata.json`
- **Use Case**: Evaluation with known correct answers

### Reference-Free Queries

- **Count**: 100 questions
- **Source**: SQuAD v2.0 validation split (50% overlap with referenced set)
- **Ground Truth**: Not included in query set
- **Use Case**: General testing and comparative evaluation

## Advanced Usage

### Adjust Concurrency

Speed up query execution with parallel requests:

```bash
uv run ragdiff run squad-demo faiss-l2 referenced-queries \
  --domains-dir examples \
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
cat > examples/squad-demo/query-sets/custom-queries.txt <<EOF
What is machine learning?
How does neural network training work?
What are transformers in NLP?
EOF

# Run with custom queries
uv run ragdiff run squad-demo faiss-l2 custom-queries --domains-dir examples
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'datasets'"

Install required dependencies:
```bash
uv pip install datasets sentence-transformers faiss-cpu numpy
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

## Distance Metrics Explained

### L2 (Euclidean) Distance

```
distance = sqrt(sum((a[i] - b[i])^2))
```

- Measures straight-line distance in vector space
- Sensitive to vector magnitude
- Common in k-NN and clustering
- Lower is better

### Inner Product (Cosine Similarity)

```
similarity = dot(a, b) / (norm(a) * norm(b))
```

- Measures angle between vectors
- With normalized vectors: `dot(a, b)` = cosine similarity
- Invariant to vector magnitude
- Higher is better

### When to Use Each

- **L2**: When vector magnitude matters (e.g., frequency-based features)
- **Inner Product/Cosine**: When direction matters more than magnitude (e.g., semantic similarity)

For most text embedding tasks, **cosine similarity** (Inner Product with normalization) is preferred because:
- It's insensitive to document length
- It focuses on semantic similarity
- It's the standard for sentence embeddings
