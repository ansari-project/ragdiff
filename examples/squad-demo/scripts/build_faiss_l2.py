#!/usr/bin/env python3
"""Build FAISS index with L2 (Euclidean) distance metric.

This script creates a FAISS index using L2 distance, which measures
Euclidean distance between vectors. Smaller distances indicate
higher similarity.
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
    output_file = data_dir / "faiss_l2.index"

    # Load embedding model
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding_dim = 384  # Dimension for all-MiniLM-L6-v2

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
        texts,
        show_progress_bar=True,
        batch_size=32,
        convert_to_numpy=True
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

    print(f"✓ Created FAISS L2 index at {output_file}")
    print(f"  Metric: L2 (Euclidean distance)")
    print(f"  Vectors: {index.ntotal}")
    print(f"  Dimensions: {index.d}")
    print("\nL2 distance characteristics:")
    print("  - Measures Euclidean distance between vectors")
    print("  - Smaller values = higher similarity")
    print("  - Sensitive to vector magnitude")
    print("  - Range: [0, ∞)")


if __name__ == "__main__":
    main()
