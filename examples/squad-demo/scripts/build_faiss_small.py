#!/usr/bin/env python3
"""Build FAISS index with small/fast embedding model.

This script creates a FAISS index using the paraphrase-MiniLM-L3-v2 model,
which is small (17MB) and fast but less accurate than larger models.
"""

import json
import sys
from pathlib import Path

try:
    import faiss
    import numpy as np
except ImportError as e:
    print(f"Error: {e}")
    print("Install dependencies with: pip install faiss-cpu numpy")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: sentence-transformers not found.")
    print("Install with: pip install sentence-transformers")
    sys.exit(1)


def main() -> None:
    """Build FAISS index with L2 distance."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    documents_file = data_dir / "documents.jsonl"

    if not documents_file.exists():
        print(f"Error: {documents_file} not found")
        print("Run setup_dataset.py first!")
        sys.exit(1)

    # Output path
    output_file = data_dir / "faiss_small.index"

    # Load embedding model (small/fast)
    print("Loading embedding model (paraphrase-MiniLM-L3-v2 - small/fast)...")
    model = SentenceTransformer("paraphrase-MiniLM-L3-v2")
    embedding_dim = 384  # Dimension for paraphrase-MiniLM-L3-v2

    # Load documents
    print(f"Loading documents from {documents_file}...")
    documents = []
    with open(documents_file, encoding="utf-8") as f:
        for line in f:
            documents.append(json.loads(line.strip()))

    print(f"Loaded {len(documents)} documents")

    # Generate embeddings
    print("Generating embeddings...")
    texts = [doc["text"] for doc in documents]
    embeddings = model.encode(
        texts, show_progress_bar=True, batch_size=32, convert_to_numpy=True
    )

    # Ensure correct dtype
    embeddings = np.array(embeddings, dtype="float32")

    print(f"Generated {len(embeddings)} embeddings with dimension {embedding_dim}")

    # Create FAISS index with L2 distance
    print("Building FAISS index with L2 (Euclidean) distance...")
    index = faiss.IndexFlatL2(embedding_dim)

    # Add vectors to index
    index.add(embeddings)

    print(f"Index created with {index.ntotal} vectors")

    # Save index
    print(f"Saving index to {output_file}...")
    faiss.write_index(index, str(output_file))

    print(f"✓ Created FAISS index (small model) at {output_file}")
    print("  Model: paraphrase-MiniLM-L3-v2")
    print("  Metric: L2 (Euclidean distance)")
    print(f"  Vectors: {index.ntotal}")
    print(f"  Dimensions: {index.d}")
    print("\nModel characteristics:")
    print("  - Small/fast model (17MB, 3 layers)")
    print("  - Lower accuracy but very fast")
    print("  - Good for speed-sensitive applications")


if __name__ == "__main__":
    main()
