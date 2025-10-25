#!/usr/bin/env python3
"""Sample questions from SQuAD dataset for RAG testing.

This script extracts a random sample of questions from the SQuAD dataset
and saves them in query set format for use with RAGDiff batch processing.

Usage:
    python sample_squad_questions.py --output squad-100-queries.json --count 100
"""

import argparse
import json
import random
import sys
from typing import Any


def load_squad_data(file_path: str) -> list[dict[str, Any]]:
    """Load and parse SQuAD dataset.

    Args:
        file_path: Path to SQuAD JSON file

    Returns:
        List of questions with metadata
    """
    print(f"Loading SQuAD data from {file_path}...")
    with open(file_path, "r") as f:
        squad_data = json.load(f)

    questions = []
    for article in squad_data["data"]:
        title = article["title"]
        for paragraph in article["paragraphs"]:
            context = paragraph["context"]
            for qa in paragraph["qas"]:
                questions.append(
                    {
                        "id": qa["id"],
                        "question": qa["question"],
                        "article_title": title,
                        "context": context,
                        "is_impossible": qa.get("is_impossible", False),
                        "answers": (
                            [a["text"] for a in qa.get("answers", [])]
                            if not qa.get("is_impossible", False)
                            else []
                        ),
                    }
                )

    print(f"Loaded {len(questions)} questions from SQuAD dataset")
    return questions


def sample_questions(
    questions: list[dict[str, Any]], count: int, answerable_only: bool = False, seed: int = None
) -> list[dict[str, Any]]:
    """Sample random questions from the dataset.

    Args:
        questions: List of all questions
        count: Number of questions to sample
        answerable_only: Only include answerable questions
        seed: Random seed for reproducibility

    Returns:
        Sampled questions
    """
    if seed is not None:
        random.seed(seed)

    # Filter if needed
    if answerable_only:
        questions = [q for q in questions if not q["is_impossible"]]
        print(f"Filtered to {len(questions)} answerable questions")

    if count > len(questions):
        print(
            f"Warning: Requested {count} questions but only {len(questions)} available"
        )
        count = len(questions)

    # Sample
    sampled = random.sample(questions, count)
    print(f"Sampled {len(sampled)} questions")
    return sampled


def save_queryset_format(questions: list[dict[str, Any]], output_path: str) -> None:
    """Save questions in RAGDiff query set format.

    Args:
        questions: Questions to save
        output_path: Output file path
    """
    queryset = {
        "queries": [
            {
                "id": q["id"],
                "query": q["question"],
                "metadata": {
                    "article_title": q["article_title"],
                    "is_impossible": q["is_impossible"],
                    "answers": q["answers"],
                }
            }
            for q in questions
        ]
    }

    with open(output_path, "w") as f:
        json.dump(queryset, f, indent=2)

    print(f"Saved {len(questions)} questions in query set format to {output_path}")


def save_questions_txt(questions: list[dict[str, Any]], output_path: str) -> None:
    """Save questions to a text file (one per line).

    Args:
        questions: Questions to save
        output_path: Output file path
    """
    with open(output_path, "w") as f:
        for q in questions:
            f.write(q["question"] + "\n")

    print(f"Saved {len(questions)} questions to {output_path}")


def save_questions_jsonl(questions: list[dict[str, Any]], output_path: str) -> None:
    """Save questions with metadata to JSONL file.

    Args:
        questions: Questions to save
        output_path: Output file path
    """
    with open(output_path, "w") as f:
        for q in questions:
            json.dump(q, f)
            f.write("\n")

    print(f"Saved {len(questions)} questions with metadata to {output_path}")


def print_statistics(questions: list[dict[str, Any]]) -> None:
    """Print statistics about the sampled questions.

    Args:
        questions: Sampled questions
    """
    answerable = sum(1 for q in questions if not q["is_impossible"])
    unanswerable = len(questions) - answerable

    # Count unique articles
    unique_articles = len(set(q["article_title"] for q in questions))

    # Average question length
    avg_length = sum(len(q["question"]) for q in questions) / len(questions)

    print("\nQuestion Statistics:")
    print(f"  Total questions: {len(questions)}")
    print(f"  Answerable: {answerable} ({answerable/len(questions)*100:.1f}%)")
    print(f"  Unanswerable: {unanswerable} ({unanswerable/len(questions)*100:.1f}%)")
    print(f"  Unique articles: {unique_articles}")
    print(f"  Average question length: {avg_length:.1f} characters")
    print(f"\nSample questions:")
    for i, q in enumerate(questions[:5], 1):
        print(f"  {i}. {q['question']}")
        if q["answers"]:
            print(f"     Answer: {q['answers'][0]}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Sample questions from SQuAD dataset for RAG testing"
    )
    parser.add_argument(
        "--squad-file",
        default="squad-dev-v2.0.json",
        help="Path to SQuAD dataset file (default: squad-dev-v2.0.json)",
    )
    parser.add_argument(
        "--output",
        default="squad-100-queries.json",
        help="Output file for questions (default: squad-100-queries.json)",
    )
    parser.add_argument(
        "--count", type=int, default=100, help="Number of questions to sample (default: 100)"
    )
    parser.add_argument(
        "--answerable-only",
        action="store_true",
        help="Only sample answerable questions",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--format",
        choices=["queryset", "txt", "jsonl"],
        default="queryset",
        help="Output format (default: queryset)",
    )

    args = parser.parse_args()

    # Check if file exists
    try:
        questions = load_squad_data(args.squad_file)
    except FileNotFoundError:
        print(f"Error: File not found: {args.squad_file}")
        print("\nTo download the SQuAD dataset, run:")
        print("  python load_squad_to_mongodb.py")
        print("\nOr download manually from:")
        print("  https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json")
        sys.exit(1)

    # Sample questions
    sampled = sample_questions(
        questions, args.count, answerable_only=args.answerable_only, seed=args.seed
    )

    # Save to file in the specified format
    if args.format == "queryset":
        save_queryset_format(sampled, args.output)
    elif args.format == "jsonl":
        save_questions_jsonl(sampled, args.output)
    else:  # txt
        save_questions_txt(sampled, args.output)

    # Print statistics
    print_statistics(sampled)

    print(f"\nDone! Use the questions with RAGDiff:")
    print(f"  uv run ragdiff batch {args.output} \\")
    print(f"    --config configs/squad-mongodb.yaml \\")
    print(f"    --output-dir results/ \\")
    print(f"    --top-k 5")


if __name__ == "__main__":
    main()
