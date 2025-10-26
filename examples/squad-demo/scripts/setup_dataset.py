#!/usr/bin/env python3
"""Download and prepare SQuAD dataset for FAISS indexing.

This script downloads a subset of the SQuAD v2.0 dataset and prepares it
for indexing with FAISS. It creates a documents.jsonl file containing
the context paragraphs from SQuAD.
"""

import json
import sys
from pathlib import Path
from typing import Any

try:
    from datasets import load_dataset
except ImportError:
    print("Error: datasets library not found. Install with: pip install datasets")
    sys.exit(1)


def main() -> None:
    """Download and prepare SQuAD dataset."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    data_dir.mkdir(exist_ok=True)

    output_file = data_dir / "documents.jsonl"

    print("Loading SQuAD v2.0 dataset from HuggingFace...")

    # Load SQuAD v2.0 validation split (smaller, good for demo)
    dataset = load_dataset("squad_v2", split="validation")

    print(f"Loaded {len(dataset)} examples")

    # Extract unique contexts (documents)
    # SQuAD has duplicate contexts, so we'll deduplicate
    contexts_seen: set[str] = set()
    documents: list[dict[str, Any]] = []

    print("Extracting unique context paragraphs...")

    for idx, example in enumerate(dataset):
        context = example["context"]

        # Skip if we've seen this context before
        if context in contexts_seen:
            continue

        contexts_seen.add(context)

        # Create document entry
        doc = {
            "id": f"squad_{len(documents)}",
            "text": context,
            "source": "SQuAD v2.0",
            "metadata": {
                "title": example.get("title", "Unknown"),
                "original_index": idx,
            }
        }
        documents.append(doc)

    print(f"Found {len(documents)} unique context paragraphs")

    # Write to JSONL
    print(f"Writing documents to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"✓ Created {output_file} with {len(documents)} documents")

    # Also save raw dataset for query generation
    raw_file = data_dir / "squad_raw.json"
    print(f"Saving raw dataset to {raw_file}...")

    raw_data = {
        "examples": [
            {
                "id": ex["id"],
                "question": ex["question"],
                "context": ex["context"],
                "answers": ex["answers"],
                "title": ex.get("title", "Unknown"),
            }
            for ex in dataset
        ]
    }

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Created {raw_file} with {len(dataset)} Q&A examples")
    print("\nDataset preparation complete!")
    print(f"  Documents: {len(documents)}")
    print(f"  Q&A pairs: {len(dataset)}")
    print(f"\nNext steps:")
    print("  1. Run build_faiss_l2.py to create L2 distance index")
    print("  2. Run build_faiss_ip.py to create Inner Product index")


if __name__ == "__main__":
    main()
