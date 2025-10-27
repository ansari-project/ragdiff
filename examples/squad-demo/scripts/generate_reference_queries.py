#!/usr/bin/env python3
"""Generate reference-based query set from SQuAD dataset.

This script creates a JSONL query set with reference answers for
correctness evaluation. Each query includes the question and the
ground truth answer from SQuAD.
"""

import json
import random
import sys
from pathlib import Path


def main() -> None:
    """Generate reference-based query set."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    squad_file = data_dir / "squad_raw.json"
    query_sets_dir = script_dir.parent / "domains" / "squad" / "query-sets"

    if not squad_file.exists():
        print(f"Error: {squad_file} not found")
        print("Run setup_dataset.py first!")
        sys.exit(1)

    # Ensure query-sets directory exists
    query_sets_dir.mkdir(parents=True, exist_ok=True)

    # Load SQuAD data
    print(f"Loading SQuAD data from {squad_file}...")
    with open(squad_file, encoding="utf-8") as f:
        squad = json.load(f)

    # Extract questions with answers
    print("Extracting questions and answers...")
    qa_pairs = []

    for example in squad["examples"]:
        # Only include questions with answers (skip impossible/unanswerable questions)
        answers = example.get("answers", {})
        if not answers or not answers.get("text"):
            continue

        # Get the first answer (they're all equivalent)
        question = example["question"]
        answer = (
            answers["text"][0] if isinstance(answers["text"], list) else answers["text"]
        )

        qa_pairs.append({"question": question, "answer": answer})

    print(f"Found {len(qa_pairs)} Q&A pairs")

    # Sample 100 random questions
    sample_size = 100
    if len(qa_pairs) > sample_size:
        print(f"Sampling {sample_size} random Q&A pairs...")
        random.seed(42)  # For reproducibility
        qa_pairs = random.sample(qa_pairs, sample_size)

    # Create JSONL output
    output_file = query_sets_dir / "test-queries-with-references.jsonl"

    print(f"Writing queries to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for qa in qa_pairs:
            entry = {
                "query": qa["question"],
                "reference": qa["answer"],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"✓ Created reference-based query set at {output_file}")
    print(f"  Total queries: {len(qa_pairs)}")
    print("  Format: JSONL with query and reference fields")
    print()
    print("Usage:")
    print("  # Run queries")
    print(
        "  uv run ragdiff run -d examples/squad-demo/domains/squad "
        "-p faiss-small -q test-queries-with-references"
    )
    print()
    print("  # Evaluate against references")
    print(
        "  uv run ragdiff evaluate -d examples/squad-demo/domains/squad "
        "-r <run-label>"
    )


if __name__ == "__main__":
    main()
