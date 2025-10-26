#!/usr/bin/env python3
"""Create a synthetic dataset for testing FAISS demo when HuggingFace is unavailable.

This script generates synthetic documents and questions for demonstration purposes.
"""

import json
import random
from pathlib import Path

# Sample topics and their content
TOPICS = {
    "Machine Learning": [
        "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
        "Supervised learning uses labeled datasets to train algorithms to classify data or predict outcomes accurately.",
        "Unsupervised learning algorithms discover hidden patterns or data groupings without the need for human intervention.",
        "Neural networks are computing systems inspired by biological neural networks that constitute animal brains.",
        "Deep learning is a subset of machine learning that uses multilayered neural networks to analyze various factors of data.",
    ],
    "Space Exploration": [
        "The International Space Station orbits Earth at an altitude of approximately 408 kilometers above sea level.",
        "Mars rovers like Curiosity and Perseverance have been exploring the Martian surface since 2012 and 2021 respectively.",
        "The James Webb Space Telescope launched in December 2021 to study the formation of the first galaxies.",
        "SpaceX's Falcon 9 is a reusable rocket system that has dramatically reduced the cost of space access.",
        "The Artemis program aims to return humans to the Moon and establish a sustainable presence by the end of the decade.",
    ],
    "Climate Science": [
        "Global temperatures have risen approximately 1.1 degrees Celsius since the pre-industrial era.",
        "The greenhouse effect is a natural process where atmospheric gases trap heat from the sun.",
        "Carbon dioxide levels in the atmosphere have increased from 280 parts per million to over 420 ppm since industrialization.",
        "Renewable energy sources like solar and wind power are becoming increasingly cost-competitive with fossil fuels.",
        "Ocean acidification occurs when seawater absorbs carbon dioxide from the atmosphere, lowering its pH.",
    ],
    "Computer Science": [
        "Python is a high-level, interpreted programming language known for its simplicity and readability.",
        "Algorithms are step-by-step procedures for solving problems or performing computations.",
        "Data structures organize and store data in a computer so it can be accessed and modified efficiently.",
        "Cloud computing delivers computing services over the internet on a pay-as-you-go basis.",
        "Cybersecurity involves protecting systems, networks, and programs from digital attacks.",
    ],
    "History": [
        "The Roman Empire reached its greatest territorial extent in 117 AD under Emperor Trajan.",
        "The Renaissance was a period of cultural rebirth in Europe spanning the 14th to 17th centuries.",
        "The Industrial Revolution began in Britain in the late 18th century and transformed manufacturing processes.",
        "World War II lasted from 1939 to 1945 and involved most of the world's nations.",
        "The fall of the Berlin Wall in 1989 symbolized the end of the Cold War era.",
    ],
}

# Question templates
QUESTION_TEMPLATES = [
    "What is {concept}?",
    "When did {event} occur?",
    "How does {process} work?",
    "What are the characteristics of {thing}?",
    "Why is {topic} important?",
]


def main() -> None:
    """Generate synthetic dataset."""
    # Set up paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    data_dir.mkdir(exist_ok=True)

    output_file = data_dir / "documents.jsonl"
    raw_file = data_dir / "squad_raw.json"

    print("Generating synthetic dataset for FAISS demo...")

    # Create documents
    documents = []
    all_examples = []

    doc_id = 0
    for topic, paragraphs in TOPICS.items():
        for para in paragraphs:
            doc = {
                "id": f"doc_{doc_id}",
                "text": para,
                "source": "Synthetic Dataset",
                "metadata": {
                    "title": topic,
                    "doc_index": doc_id,
                }
            }
            documents.append(doc)

            # Generate a question for this paragraph
            # Extract key phrases
            words = para.split()
            if len(words) > 10:
                # Create a simple question
                example = {
                    "id": f"question_{doc_id}",
                    "question": f"What does the text say about {topic.lower()}?",
                    "context": para,
                    "answers": {"text": [para.split('.')[0] if '.' in para else para[:50]]},
                    "title": topic,
                }
                all_examples.append(example)

            doc_id += 1

    print(f"Generated {len(documents)} documents")

    # Write documents
    print(f"Writing documents to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"✓ Created {output_file} with {len(documents)} documents")

    # Write raw data
    print(f"Saving raw dataset to {raw_file}...")
    raw_data = {"examples": all_examples}

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Created {raw_file} with {len(all_examples)} Q&A examples")
    print("\nSynthetic dataset creation complete!")
    print(f"  Documents: {len(documents)}")
    print(f"  Q&A pairs: {len(all_examples)}")
    print(f"\nNext steps:")
    print("  1. Run build_faiss_l2.py to create L2 distance index")
    print("  2. Run build_faiss_ip.py to create Inner Product index")


if __name__ == "__main__":
    main()
