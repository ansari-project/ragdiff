#!/usr/bin/env python3
"""Build FAISS indices with simple TF-IDF embeddings (no external models needed).

This script creates both L2 and Inner Product indices using sklearn's TfidfVectorizer
for embeddings, avoiding the need to download external models.
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
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    print("Error: scikit-learn not found.")
    print("Install with: pip install scikit-learn")
    sys.exit(1)


def main() -> None:
    """Build FAISS indices with TF-IDF embeddings."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    documents_file = data_dir / "documents.jsonl"

    if not documents_file.exists():
        print(f"Error: {documents_file} not found")
        print("Run setup_synthetic_dataset.py first!")
        sys.exit(1)

    # Load documents
    print(f"Loading documents from {documents_file}...")
    documents = []
    with open(documents_file, encoding="utf-8") as f:
        for line in f:
            documents.append(json.loads(line.strip()))

    print(f"Loaded {len(documents)} documents")

    # Generate TF-IDF embeddings
    print("Generating TF-IDF embeddings...")
    texts = [doc["text"] for doc in documents]

    # Use TF-IDF with limited features for simplicity
    vectorizer = TfidfVectorizer(max_features=384, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Convert to dense numpy array
    embeddings = tfidf_matrix.toarray().astype('float32')
    embedding_dim = embeddings.shape[1]

    print(f"Generated {len(embeddings)} embeddings with dimension {embedding_dim}")

    # Build L2 index
    print("\n" + "="*60)
    print("Building FAISS index with L2 (Euclidean) distance...")
    print("="*60)

    index_l2 = faiss.IndexFlatL2(embedding_dim)
    index_l2.add(embeddings)

    output_l2 = data_dir / "faiss_l2.index"
    faiss.write_index(index_l2, str(output_l2))

    print(f"✓ Created FAISS L2 index at {output_l2}")
    print(f"  Metric: L2 (Euclidean distance)")
    print(f"  Vectors: {index_l2.ntotal}")
    print(f"  Dimensions: {index_l2.d}")

    # Build Inner Product index
    print("\n" + "="*60)
    print("Building FAISS index with Inner Product (cosine similarity)...")
    print("="*60)

    # Normalize embeddings for proper cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings_normalized = embeddings / (norms + 1e-10)  # Avoid division by zero

    index_ip = faiss.IndexFlatIP(embedding_dim)
    index_ip.add(embeddings_normalized)

    output_ip = data_dir / "faiss_ip.index"
    faiss.write_index(index_ip, str(output_ip))

    print(f"✓ Created FAISS Inner Product index at {output_ip}")
    print(f"  Metric: Inner Product (cosine similarity with normalized vectors)")
    print(f"  Vectors: {index_ip.ntotal}")
    print(f"  Dimensions: {index_ip.d}")

    # Save vectorizer for query encoding
    print("\n" + "="*60)
    print("Saving TF-IDF vectorizer...")
    print("="*60)

    import pickle
    vectorizer_file = data_dir / "tfidf_vectorizer.pkl"
    with open(vectorizer_file, "wb") as f:
        pickle.dump(vectorizer, f)

    print(f"✓ Saved vectorizer to {vectorizer_file}")

    print("\n" + "="*60)
    print("FAISS index creation complete!")
    print("="*60)
    print("\nYou can now run RAGDiff comparisons:")
    print("  uv run ragdiff run squad-demo faiss-l2 referenced-queries --domains-dir examples")
    print("  uv run ragdiff run squad-demo faiss-ip referenced-queries --domains-dir examples")


if __name__ == "__main__":
    main()
