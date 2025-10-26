#!/usr/bin/env python3
"""Generate query sets from SQuAD dataset.

This script generates two types of query sets:
1. Referenced: Queries with ground truth answers (for evaluation)
2. Reference-free: Queries without answers (for general testing)

Each query set contains 100 questions sampled from the SQuAD dataset.
"""

import json
import random
from pathlib import Path


def main() -> None:
    """Generate query sets."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    query_sets_dir = script_dir.parent / "query-sets"
    query_sets_dir.mkdir(exist_ok=True)

    raw_file = data_dir / "squad_raw.json"

    if not raw_file.exists():
        print(f"Error: {raw_file} not found")
        print("Run setup_dataset.py first!")
        return

    # Load raw dataset
    print(f"Loading raw dataset from {raw_file}...")
    with open(raw_file, encoding="utf-8") as f:
        data = json.load(f)

    examples = data["examples"]
    print(f"Loaded {len(examples)} Q&A examples")

    # Filter out examples without answers (impossible questions in SQuAD v2)
    answerable = [ex for ex in examples if ex["answers"]["text"]]
    print(f"Found {len(answerable)} answerable questions")

    # Randomly sample 150 examples (we'll use 100 for each set with some overlap)
    random.seed(42)  # For reproducibility
    sampled = random.sample(answerable, min(150, len(answerable)))

    # Split into two sets
    referenced_examples = sampled[:100]
    reference_free_examples = sampled[50:150]  # 50% overlap

    # Generate referenced query set (with ground truth)
    print("\nGenerating referenced query set...")
    referenced_file = query_sets_dir / "referenced-queries.txt"
    referenced_meta_file = data_dir / "referenced-queries-metadata.json"

    with open(referenced_file, "w", encoding="utf-8") as f:
        for ex in referenced_examples:
            f.write(ex["question"] + "\n")

    # Save metadata with ground truth answers
    metadata = {
        "type": "referenced",
        "count": len(referenced_examples),
        "queries": [
            {
                "question": ex["question"],
                "answers": ex["answers"]["text"],
                "context": ex["context"],
                "title": ex["title"],
                "id": ex["id"],
            }
            for ex in referenced_examples
        ]
    }

    with open(referenced_meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"✓ Created {referenced_file} ({len(referenced_examples)} queries)")
    print(f"✓ Created {referenced_meta_file} (with ground truth answers)")

    # Generate reference-free query set
    print("\nGenerating reference-free query set...")
    reference_free_file = query_sets_dir / "reference-free-queries.txt"

    with open(reference_free_file, "w", encoding="utf-8") as f:
        for ex in reference_free_examples:
            f.write(ex["question"] + "\n")

    print(f"✓ Created {reference_free_file} ({len(reference_free_examples)} queries)")

    print("\n" + "="*60)
    print("Query set generation complete!")
    print("="*60)
    print(f"\nReferenced queries: {len(referenced_examples)}")
    print(f"  File: {referenced_file}")
    print(f"  Metadata: {referenced_meta_file}")
    print(f"  Use for: Evaluation with ground truth answers")
    print(f"\nReference-free queries: {len(reference_free_examples)}")
    print(f"  File: {reference_free_file}")
    print(f"  Use for: General testing and comparison")
    print("\nExample questions:")
    print(f"  1. {referenced_examples[0]['question']}")
    print(f"  2. {referenced_examples[1]['question']}")
    print(f"  3. {referenced_examples[2]['question']}")


if __name__ == "__main__":
    main()
