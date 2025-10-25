#!/usr/bin/env python3
"""Load SQuAD dataset into local MongoDB with vector embeddings.

This script downloads the SQuAD v2.0 dataset, generates embeddings for each
context passage using sentence-transformers (local), and stores them in
local MongoDB.

Prerequisites:
- Local MongoDB installation
- sentence-transformers library
- Environment variable: MONGODB_URI (default: mongodb://localhost:27017/)

Usage:
    python load_squad_to_mongodb.py --database squad_db --collection contexts
"""

import argparse
import json
import os
import sys
import urllib.request
from typing import Any

# Check for required packages
try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:
    print("Error: pymongo is required. Install with: pip install pymongo")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Error: sentence-transformers is required. Install with: pip install sentence-transformers")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Warning: tqdm not found. Install with: pip install tqdm for progress bars")
    tqdm = None


# SQuAD v2.0 dataset URL
SQUAD_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json"


def download_squad_dataset(output_path: str = "squad-dev-v2.0.json") -> str:
    """Download SQuAD v2.0 development dataset.

    Args:
        output_path: Where to save the downloaded dataset

    Returns:
        Path to downloaded file
    """
    if os.path.exists(output_path):
        print(f"Dataset already exists at {output_path}")
        return output_path

    print(f"Downloading SQuAD v2.0 dataset from {SQUAD_URL}...")
    urllib.request.urlretrieve(SQUAD_URL, output_path)
    print(f"Downloaded to {output_path}")
    return output_path


def load_squad_data(file_path: str) -> list[dict[str, Any]]:
    """Load and parse SQuAD dataset.

    Args:
        file_path: Path to SQuAD JSON file

    Returns:
        List of context documents with metadata
    """
    print(f"Loading SQuAD data from {file_path}...")
    with open(file_path, "r") as f:
        squad_data = json.load(f)

    documents = []
    for article in squad_data["data"]:
        title = article["title"]
        for paragraph in article["paragraphs"]:
            context = paragraph["context"]
            # Extract all QA pairs for this context
            qas = []
            for qa in paragraph["qas"]:
                qas.append(
                    {
                        "id": qa["id"],
                        "question": qa["question"],
                        "is_impossible": qa.get("is_impossible", False),
                        "answers": (
                            [a["text"] for a in qa.get("answers", [])]
                            if not qa.get("is_impossible", False)
                            else []
                        ),
                    }
                )

            documents.append(
                {
                    "text": context,
                    "source": title,
                    "article_title": title,
                    "questions": qas,
                    "num_questions": len(qas),
                }
            )

    print(f"Loaded {len(documents)} context passages from {len(squad_data['data'])} articles")
    return documents


def generate_embeddings(
    documents: list[dict[str, Any]], model_name: str = "all-MiniLM-L6-v2", batch_size: int = 32
) -> list[dict[str, Any]]:
    """Generate embeddings for documents using sentence-transformers.

    Args:
        documents: List of documents to embed
        model_name: Sentence-transformer model to use
        batch_size: Number of documents to process at once

    Returns:
        Documents with embeddings added
    """
    print(f"Loading embedding model: {model_name}...")
    print("(First run will download the model, subsequent runs use cached version)")

    model = SentenceTransformer(model_name)

    print(f"Generating embeddings for {len(documents)} documents...")
    texts = [doc["text"] for doc in documents]

    # Generate embeddings in batches with progress bar
    if tqdm:
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
    else:
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

    # Add embeddings to documents
    for i, embedding in enumerate(embeddings):
        documents[i]["embedding"] = embedding.tolist()

    embedded_count = sum(1 for doc in documents if "embedding" in doc)
    print(f"Generated embeddings for {embedded_count}/{len(documents)} documents")
    print(f"Embedding dimensions: {len(embeddings[0])}")

    return documents


def insert_into_mongodb(
    documents: list[dict[str, Any]], connection_uri: str, database: str, collection: str
) -> None:
    """Insert documents into MongoDB collection.

    Args:
        documents: Documents to insert
        connection_uri: MongoDB connection string
        database: Database name
        collection: Collection name
    """
    print(f"Connecting to MongoDB at {connection_uri}...")
    client = MongoClient(connection_uri)

    try:
        # Test connection
        client.admin.command("ping")
        print("Connected to MongoDB successfully")

        db = client[database]
        coll = db[collection]

        # Drop existing collection to start fresh
        print(f"Dropping existing collection {database}.{collection} if it exists...")
        coll.drop()

        # Insert documents
        print(f"Inserting {len(documents)} documents into {database}.{collection}...")
        if tqdm:
            # Insert with progress bar
            batch_size = 100
            for i in tqdm(range(0, len(documents), batch_size), desc="Inserting batches"):
                batch = documents[i : i + batch_size]
                coll.insert_many(batch)
        else:
            coll.insert_many(documents)

        print(f"Successfully inserted {len(documents)} documents")

        # Print sample document
        sample = coll.find_one()
        if sample:
            print("\nSample document:")
            print(f"  Title: {sample.get('article_title')}")
            print(f"  Text length: {len(sample.get('text', ''))}")
            print(f"  Embedding dimensions: {len(sample.get('embedding', []))}")
            print(f"  Number of questions: {sample.get('num_questions')}")

    except PyMongoError as e:
        print(f"MongoDB error: {e}")
        raise
    finally:
        client.close()


def create_vector_index_instructions(database: str, collection: str, dimensions: int) -> None:
    """Print instructions for creating a vector search index.

    Args:
        database: Database name
        collection: Collection name
        dimensions: Embedding dimensions
    """
    print("\n" + "=" * 80)
    print("NEXT STEP: Create Vector Index")
    print("=" * 80)
    print("\nFor local MongoDB (Community Edition), use a basic 2dsphere index:")
    print("\n1. Open mongosh:")
    print("   mongosh")
    print(f"\n2. Switch to database and create index:")
    print(f"   use {database}")
    print(f"   db.{collection}.createIndex({{ \"embedding\": \"2dsphere\" }}, {{ name: \"vector_index\" }})")
    print("\nNote: MongoDB Community Edition has basic vector support.")
    print("For advanced vector search ($vectorSearch), consider MongoDB Atlas.")
    print(f"\nEmbedding dimensions: {dimensions}")
    print("=" * 80 + "\n")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Load SQuAD dataset into MongoDB with sentence-transformer embeddings"
    )
    parser.add_argument(
        "--database", default="squad_db", help="MongoDB database name (default: squad_db)"
    )
    parser.add_argument(
        "--collection",
        default="contexts",
        help="MongoDB collection name (default: contexts)",
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformer model (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--squad-file",
        default="squad-dev-v2.0.json",
        help="Path to SQuAD dataset file (will download if not exists)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading dataset (use existing file)",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of documents to process (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)"
    )

    args = parser.parse_args()

    # Check environment variable (with default for local MongoDB)
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    print(f"Using MongoDB URI: {mongodb_uri}")

    # Download SQuAD dataset
    if not args.skip_download or not os.path.exists(args.squad_file):
        download_squad_dataset(args.squad_file)

    # Load dataset
    documents = load_squad_data(args.squad_file)

    # Limit documents if requested (for testing)
    if args.limit:
        print(f"Limiting to {args.limit} documents (testing mode)")
        documents = documents[: args.limit]

    # Generate embeddings using sentence-transformers
    documents = generate_embeddings(documents, model_name=args.model, batch_size=args.batch_size)

    # Filter out documents that failed to get embeddings
    documents = [doc for doc in documents if "embedding" in doc]

    if not documents:
        print("Error: No documents with embeddings to insert")
        sys.exit(1)

    # Get embedding dimensions from first document
    dimensions = len(documents[0]["embedding"])

    # Insert into MongoDB
    insert_into_mongodb(documents, mongodb_uri, args.database, args.collection)

    # Print instructions for creating vector index
    create_vector_index_instructions(args.database, args.collection, dimensions)

    print("\nDone! Your SQuAD dataset is now in MongoDB.")
    print(
        f"Use the MongoDB adapter in RAGDiff with database='{args.database}', collection='{args.collection}'"
    )
    print(f"\nCosts: FREE! Everything runs locally with sentence-transformers.")


if __name__ == "__main__":
    main()
