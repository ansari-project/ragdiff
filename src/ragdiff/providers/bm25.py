"""BM25 keyword search provider for RAGDiff v2.0.

A local keyword-based search provider using BM25s (Best Match 25).
Provides efficient keyword search without embeddings or vector similarity.

Configuration:
    index_path: Path to BM25 index file (string, required - will be created if missing)
    documents_path: Path to JSONL documents file (string, required)
    variant: BM25 variant ("robertson", "lucene", "bm25l", "bm25+", "atire", default: "lucene")
    k1: Term frequency saturation parameter (float, default: 1.5)
    b: Length normalization parameter (float, default: 0.75)

Example:
    >>> provider = BM25Provider(config={
    ...     "index_path": "/path/to/index.bm25",
    ...     "documents_path": "/path/to/docs.jsonl",
    ...     "variant": "lucene",
    ...     "k1": 1.5,
    ...     "b": 0.75
    ... })
    >>> chunks = provider.search("What is BM25?", top_k=5)
"""

import json
from pathlib import Path

from ..core.errors import ConfigError, RunError
from ..core.logging import get_logger
from ..core.models_v2 import RetrievedChunk
from .abc import Provider

logger = get_logger(__name__)


class BM25Provider(Provider):
    """BM25 keyword-based search provider.

    Uses BM25s for efficient keyword search over documents.
    Documents are stored in JSONL format with structure:
    {"id": "...", "text": "...", "source": "...", "metadata": {...}}
    """

    def __init__(self, config: dict):
        """Initialize BM25 provider.

        Args:
            config: Configuration dictionary

        Raises:
            ConfigError: If required config missing or invalid
        """
        super().__init__(config)

        # Validate required fields
        required = ["index_path", "documents_path"]
        for field in required:
            if field not in config:
                raise ConfigError(f"BM25 provider requires '{field}' in config")

        self.index_path = Path(config["index_path"])
        self.documents_path = Path(config["documents_path"])
        self.variant = config.get("variant", "lucene")
        self.k1 = config.get("k1", 1.5)
        self.b = config.get("b", 0.75)

        # Import BM25s
        try:
            import bm25s

            self.bm25s = bm25s
        except ImportError as e:
            raise ConfigError(
                "bm25s not installed. Install with: pip install bm25s"
            ) from e

        # Load documents first (needed for indexing)
        self._load_documents()

        # Load or build index
        if self.index_path.exists():
            self._load_index()
        else:
            logger.info(f"Index not found at {self.index_path}, building new index...")
            self._build_index()
            self._save_index()

        logger.debug(
            f"Initialized BM25 provider: {len(self.documents)} docs, "
            f"variant={self.variant}, k1={self.k1}, b={self.b}"
        )

    def _load_documents(self) -> None:
        """Load documents from JSONL file.

        Raises:
            ConfigError: If documents cannot be loaded
        """
        if not self.documents_path.exists():
            raise ConfigError(f"Documents file not found at: {self.documents_path}")

        try:
            self.documents = []
            self.document_texts = []

            with open(self.documents_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        doc = json.loads(line.strip())
                        # Validate document structure
                        if "id" not in doc or "text" not in doc:
                            logger.warning(
                                f"Line {line_num}: Document missing 'id' or 'text' field, skipping"
                            )
                            continue
                        self.documents.append(doc)
                        self.document_texts.append(doc["text"])
                    except json.JSONDecodeError as e:
                        logger.warning(f"Line {line_num}: Invalid JSON, skipping: {e}")
                        continue

            logger.info(
                f"Loaded {len(self.documents)} documents from {self.documents_path}"
            )

        except Exception as e:
            raise ConfigError(f"Failed to load documents: {e}") from e

    def _build_index(self) -> None:
        """Build BM25 index from documents.

        Raises:
            ConfigError: If index building fails
        """
        try:
            logger.info(f"Building BM25 index for {len(self.documents)} documents...")

            # Tokenize documents
            corpus_tokens = self.bm25s.tokenize(self.document_texts, stopwords="en")

            # Create retriever with specified variant
            self.retriever = self.bm25s.BM25(method=self.variant, k1=self.k1, b=self.b)

            # Index the corpus tokens
            self.retriever.index(corpus_tokens)

            logger.info(f"Built BM25 index with {len(self.documents)} documents")

        except Exception as e:
            raise ConfigError(f"Failed to build BM25 index: {e}") from e

    def _save_index(self) -> None:
        """Save BM25 index to disk.

        Raises:
            ConfigError: If index saving fails
        """
        try:
            # Ensure parent directory exists
            self.index_path.parent.mkdir(parents=True, exist_ok=True)

            # Save index
            self.retriever.save(str(self.index_path))
            logger.info(f"Saved BM25 index to {self.index_path}")

        except Exception as e:
            raise ConfigError(f"Failed to save BM25 index: {e}") from e

    def _load_index(self) -> None:
        """Load BM25 index from disk.

        Raises:
            ConfigError: If index cannot be loaded
        """
        try:
            self.retriever = self.bm25s.BM25.load(str(self.index_path))
            logger.info(f"Loaded BM25 index from {self.index_path}")

        except Exception as e:
            raise ConfigError(f"Failed to load BM25 index: {e}") from e

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Search BM25 index for relevant documents.

        Args:
            query: Search query text
            top_k: Maximum results to return

        Returns:
            List of RetrievedChunk objects

        Raises:
            RunError: If search fails
        """
        try:
            # Tokenize query
            query_tokens = self.bm25s.tokenize([query], stopwords="en")

            # Search index - returns (indices, scores) as 2D arrays by default
            indices, scores = self.retriever.retrieve(query_tokens, k=top_k)

            # Convert to RetrievedChunk objects
            # indices[0] and scores[0] because we only have one query
            chunks = []
            for idx, score in zip(indices[0], scores[0]):
                # Convert numpy int to Python int
                doc_idx = int(idx)

                # Skip invalid indices
                if doc_idx < 0 or doc_idx >= len(self.documents):
                    logger.warning(f"Invalid index {doc_idx}, skipping")
                    continue

                doc = self.documents[doc_idx]

                # BM25 scores are already similarity scores (higher is better)
                # Normalize to 0-1 range using sigmoid-like function
                normalized_score = float(score) / (1.0 + float(score))

                chunk = RetrievedChunk(
                    content=doc["text"],
                    score=normalized_score,
                    metadata={
                        "id": str(doc["id"]),
                        "source": doc.get("source", "BM25"),
                        **(doc.get("metadata", {})),
                        "bm25_score": float(score),
                        "bm25_index": doc_idx,
                        "bm25_variant": self.variant,
                    },
                )
                chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            raise RunError(f"BM25 search failed: {e}") from e


# Register the provider
from .registry import register_tool  # noqa: E402

register_tool("bm25", BM25Provider)
