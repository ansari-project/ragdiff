# Rebuilding FAISS Indices with Different Embedding Models

The demo now compares **two different embedding models** to show quality differences:

## Models

- **faiss-small**: `paraphrase-MiniLM-L3-v2` (17MB, 384 dims, 3 layers, fast but less accurate)
- **faiss-large**: `all-MiniLM-L12-v2` (120MB, 384 dims, 12 layers, slower but more accurate)

## Steps to Rebuild

1. **Enter the demo environment:**
   ```bash
   cd examples/squad-demo
   source .venv/bin/activate  # or use: uv run python
   ```

2. **Build the small model index:**
   ```bash
   uv run python scripts/build_faiss_l2.py
   ```
   This creates `data/faiss_small.index` using paraphrase-MiniLM-L3-v2

3. **Build the large model index:**
   ```bash
   uv run python scripts/build_faiss_ip.py
   ```
   This creates `data/faiss_large.index` using all-mpnet-base-v2

4. **Run queries against both providers:**
   ```bash
   cd ../..  # Back to project root
   uv run ragdiff run squad-demo faiss-small test-queries --domains-dir examples
   uv run ragdiff run squad-demo faiss-large test-queries --domains-dir examples
   ```

5. **Compare the results:**
   ```bash
   uv run ragdiff compare squad-demo <run-id-1> <run-id-2> \
     --domains-dir examples \
     --format markdown \
     --output examples/squad-demo/comparison-report.md
   ```

## Expected Results

The larger model should show:
- Better retrieval accuracy (higher quality scores)
- More wins vs the small model
- But slower query times

The comparison report will show which model performs better on the SQuAD dataset!
