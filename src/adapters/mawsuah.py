"""Mawsuah adapter for Vectara-based search."""

import json
import time
from typing import List, Dict, Any, Optional
import logging
import requests

from .base import BaseRagTool
from ..core.models import RagResult, ToolConfig

logger = logging.getLogger(__name__)


class MawsuahAdapter(BaseRagTool):
    """Adapter for Mawsuah (Vectara) search tool."""

    def __init__(self, config: ToolConfig):
        """Initialize Mawsuah adapter.

        Args:
            config: Tool configuration
        """
        super().__init__(config)
        self.description = "Queries an encyclopedia of Islamic jurisprudence (fiqh)"

    def search(self, query: str, top_k: int = 5) -> List[RagResult]:
        """Search Mawsuah/Vectara for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of normalized RagResult objects
        """
        try:
            # Prepare Vectara API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "customer-id": self.customer_id
            }

            # Vectara query API format
            request_body = {
                "query": [
                    {
                        "query": query,
                        "num_results": top_k,
                        "corpus_key": [
                            {
                                "customer_id": self.customer_id,
                                "corpus_id": self.corpus_id
                            }
                        ]
                    }
                ]
            }

            # Make API request
            response = requests.post(
                f"{self.base_url}/v1/query",
                headers=headers,
                json=request_body,
                timeout=self.timeout
            )

            response.raise_for_status()
            data = response.json()

            # Parse Vectara response
            results = []
            if "responseSet" in data and len(data["responseSet"]) > 0:
                response_set = data["responseSet"][0]

                for doc in response_set.get("response", [])[:top_k]:
                    # Extract text from document
                    text = doc.get("text", "")

                    # Get metadata
                    metadata = doc.get("metadata", [])
                    doc_metadata = {}
                    for item in metadata:
                        if isinstance(item, dict):
                            doc_metadata[item.get("name", "")] = item.get("value", "")

                    # Create normalized result
                    result = RagResult(
                        id=doc.get("documentIndex", f"doc_{len(results)}"),
                        text=text,
                        score=self._normalize_score(doc.get("score", 0.0)),
                        source=doc_metadata.get("source", "Mawsuah"),
                        metadata=doc_metadata
                    )
                    results.append(result)

                # Add summary if available
                if response_set.get("summary"):
                    summary_text = " ".join(
                        s.get("text", "") for s in response_set.get("summary", [])
                    )
                    if summary_text:
                        # Add summary as first result
                        summary_result = RagResult(
                            id="summary",
                            text=summary_text,
                            score=1.0,  # Give summary highest score
                            source="Mawsuah Summary",
                            metadata={"type": "summary"}
                        )
                        results.insert(0, summary_result)

            return results

        except requests.exceptions.RequestException as e:
            logger.error(f"Mawsuah API request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Mawsuah search: {str(e)}")
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
                        "source": result.source or "Mawsuah",
                        "score": result.score,
                        "metadata": result.metadata or {}
                    }
                    ref_list.append(ref)

        return ref_list