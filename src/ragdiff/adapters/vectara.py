"""Vectara adapter for RAG search.

This adapter connects to the Vectara platform and can be used with different
corpora (e.g., Tafsir, Mawsuah) by configuring the corpus_id.
"""

import json
import time
from typing import List, Dict, Any, Optional
import logging
import requests

from .base import BaseRagTool
from ..core.models import RagResult, ToolConfig

logger = logging.getLogger(__name__)


class VectaraAdapter(BaseRagTool):
    """Adapter for Vectara RAG platform.

    Can be configured for different corpora (Tafsir, Mawsuah) via corpus_id.
    """

    def __init__(self, config: ToolConfig):
        """Initialize Vectara adapter.

        Args:
            config: Tool configuration
        """
        super().__init__(config)
        # Description can be customized based on corpus
        if "tafsir" in str(self.corpus_id).lower():
            self.description = "Queries Quranic commentaries (tafsirs)"
        else:
            self.description = "Queries an encyclopedia of Islamic jurisprudence (fiqh)"

    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        """Search Vectara for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        try:
            # Prepare Vectara v2 API request
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": self.api_key
            }

            # Vectara v2 API format
            request_body = {
                "query": query,
                "search": {
                    "corpora": [
                        {
                            "corpus_key": self.corpus_id
                        }
                    ],
                    "limit": top_k
                }
            }

            # Make API request
            response = requests.post(
                f"{self.base_url}/v2/query",
                headers=headers,
                json=request_body,
                timeout=self.timeout
            )

            response.raise_for_status()
            data = response.json()

            # Parse Vectara v2 response
            results = []
            for i, doc in enumerate(data.get("search_results", [])[:top_k]):
                # Extract text and metadata
                text = doc.get("text", "")
                score = doc.get("score", 0.0)

                # Combine part and document metadata
                metadata = {}
                if doc.get("part_metadata"):
                    metadata.update(doc["part_metadata"])
                if doc.get("document_metadata"):
                    metadata.update(doc["document_metadata"])

                # Determine source from metadata
                source = metadata.get("tafsir", "Tafsir")
                if metadata.get("surah"):
                    source = f"{source} - Surah {metadata['surah']}"

                # Create normalized result
                result = RagResult(
                    id=doc.get("document_id", f"doc_{i}"),
                    text=text,
                    score=self._normalize_score(score),
                    source=source,
                    metadata=metadata
                )
                results.append(result)

            # Check for summary in v2 response
            if data.get("summary"):
                summary_text = data.get("summary", {}).get("text", "")
                if summary_text:
                    summary_result = RagResult(
                        id="summary",
                        text=summary_text,
                        score=1.0,
                        source="Summary",
                        metadata={"type": "summary"}
                    )
                    results.insert(0, summary_result)

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Vectara API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Vectara search: {str(e)}")
            raise

    def format_as_ref_list(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format results as reference list for Claude.

        Args:
            results: Raw API response

        Returns:
            List of reference documents
        """
        ref_list = []

        if results.get("success") and results.get("results"):
            for result in results["results"]:
                if isinstance(result, RagResult):
                    ref = {
                        "text": result.text,
                        "source": result.source or "Vectara",
                        "score": result.score,
                        "metadata": result.metadata or {}
                    }
                    ref_list.append(ref)

        return ref_list