#!/usr/bin/env python3
"""Build FAISS index with Inner Product (cosine similarity) metric.

This script creates a FAISS index using Inner Product, which when used
with normalized vectors is equivalent to cosine similarity. Higher
scores indicate higher similarity.
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
    """Build FAISS index with Inner Product."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    documents_file = data_dir / "documents.jsonl"

    if not documents_file.exists():
        print(f"Error: {documents_file} not found")
        print("Run setup_dataset.py first!")
        sys.exit(1)

    # Output path
    output_file = data_dir / "faiss_ip.index"

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
        convert_to_numpy=True,
        normalize_embeddings=True  # Normalize for proper cosine similarity
    )

    # Ensure correct dtype
    embeddings = np.array(embeddings, dtype="float32")

    print(f"Generated {len(embeddings)} normalized embeddings with dimension {embedding_dim}")

    # Create FAISS index with Inner Product
    print("Building FAISS index with Inner Product (cosine similarity)...")
    index = faiss.IndexFlatIP(embedding_dim)

    # Add vectors to index
    index.add(embeddings)

    print(f"Index created with {index.ntotal} vectors")

    # Save index
    print(f"Saving index to {output_file}...")
    faiss.write_index(index, str(output_file))

    print(f"✓ Created FAISS Inner Product index at {output_file}")
    print(f"  Metric: Inner Product (cosine similarity with normalized vectors)")
    print(f"  Vectors: {index.ntotal}")
    print(f"  Dimensions: {index.d}")
    print("\nInner Product characteristics:")
    print("  - Measures dot product between vectors")
    print("  - With normalized vectors = cosine similarity")
    print("  - Higher values = higher similarity")
    print("  - Range: [-1, 1] for normalized vectors")


if __name__ == "__main__":
    main()
