#!/usr/bin/env python3
"""Load SQuAD dataset into MongoDB Atlas with vector embeddings.

This script downloads the SQuAD v2.0 dataset, generates embeddings for each
context passage using OpenAI's embedding API, and stores them in MongoDB Atlas
with a vector search index.

Prerequisites:
- MongoDB Atlas cluster (M10+ for vector search)
- OpenAI API key
- Environment variables: MONGODB_URI, OPENAI_API_KEY

Usage:
    python load_squad_to_mongodb.py --database squad_db --collection contexts
"""

import argparse
import json
import os
import sys
import time
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
    import openai
except ImportError:
    print("Error: openai is required. Install with: pip install openai")
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
    documents: list[dict[str, Any]], api_key: str, model: str = "text-embedding-3-small", batch_size: int = 100
) -> list[dict[str, Any]]:
    """Generate embeddings for documents using OpenAI API.

    Args:
        documents: List of documents to embed
        api_key: OpenAI API key
        model: Embedding model to use
        batch_size: Number of documents to process at once

    Returns:
        Documents with embeddings added
    """
    print(f"Generating embeddings using {model}...")
    client = openai.OpenAI(api_key=api_key)

    iterator = tqdm(range(0, len(documents), batch_size), desc="Embedding batches") if tqdm else range(
        0, len(documents), batch_size
    )

    for i in iterator:
        batch = documents[i : i + batch_size]
        texts = [doc["text"] for doc in batch]

        try:
            response = client.embeddings.create(model=model, input=texts)

            for j, embedding_data in enumerate(response.data):
                documents[i + j]["embedding"] = embedding_data.embedding

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            print(f"\nError generating embeddings for batch {i}: {e}")
            # Continue with next batch
            continue

    embedded_count = sum(1 for doc in documents if "embedding" in doc)
    print(f"Generated embeddings for {embedded_count}/{len(documents)} documents")
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
    print(f"Connecting to MongoDB...")
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


def create_vector_index_instructions(database: str, collection: str, model: str) -> None:
    """Print instructions for creating a vector search index.

    Args:
        database: Database name
        collection: Collection name
        model: Embedding model used (determines dimensions)
    """
    # Determine embedding dimensions based on model
    dimensions = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }.get(model, 1536)

    index_definition = {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": dimensions,
                "similarity": "dotProduct",
            },
            {"type": "filter", "path": "article_title"},
            {"type": "filter", "path": "num_questions"},
        ]
    }

    print("\n" + "=" * 80)
    print("NEXT STEP: Create Vector Search Index")
    print("=" * 80)
    print("\nTo enable vector search, create an Atlas Search index with this definition:")
    print("\n1. Go to your MongoDB Atlas cluster")
    print(f"2. Navigate to: Database > {database} > {collection}")
    print("3. Click 'Create Index' > 'Atlas Vector Search'")
    print("4. Use this index definition:\n")
    print("Index Name: vector_index")
    print("\nIndex Definition (JSON):")
    print(json.dumps(index_definition, indent=2))
    print("\n5. Click 'Create Search Index'")
    print("\nAlternatively, use the Atlas CLI or API to create the index programmatically.")
    print(
        f"\nNote: The embedding dimensions ({dimensions}) match the model '{model}'."
    )
    print("=" * 80 + "\n")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Load SQuAD dataset into MongoDB with embeddings"
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
        default="text-embedding-3-small",
        help="OpenAI embedding model (default: text-embedding-3-small)",
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

    args = parser.parse_args()

    # Check environment variables
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        print("Error: MONGODB_URI environment variable is not set")
        print("Set it to your MongoDB Atlas connection string:")
        print("  export MONGODB_URI='mongodb+srv://user:pass@cluster.mongodb.net/'")
        sys.exit(1)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable is not set")
        print("Set it to your OpenAI API key:")
        print("  export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    # Download SQuAD dataset
    if not args.skip_download or not os.path.exists(args.squad_file):
        download_squad_dataset(args.squad_file)

    # Load dataset
    documents = load_squad_data(args.squad_file)

    # Limit documents if requested (for testing)
    if args.limit:
        print(f"Limiting to {args.limit} documents (testing mode)")
        documents = documents[: args.limit]

    # Generate embeddings
    documents = generate_embeddings(documents, openai_api_key, model=args.model)

    # Filter out documents that failed to get embeddings
    documents = [doc for doc in documents if "embedding" in doc]

    if not documents:
        print("Error: No documents with embeddings to insert")
        sys.exit(1)

    # Insert into MongoDB
    insert_into_mongodb(documents, mongodb_uri, args.database, args.collection)

    # Print instructions for creating vector index
    create_vector_index_instructions(args.database, args.collection, args.model)

    print("\nDone! Your SQuAD dataset is now in MongoDB.")
    print(
        f"Use the MongoDB adapter in RAGDiff with database='{args.database}', collection='{args.collection}'"
    )


if __name__ == "__main__":
    main()
