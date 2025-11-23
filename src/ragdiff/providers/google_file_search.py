import os
from typing import List

from google import genai
from google.genai import types

from ..core.errors import ConfigError, RunError
from ..core.models import RetrievedChunk, SearchResult
from ..core.pricing import calculate_llm_cost, count_tokens
from .abc import Provider


class GoogleFileSearchProvider(Provider):
    """
    Provider for Google's File Search API (via Gemini API).

    Configuration:
        api_key: Google Cloud API key (optional, defaults to env var GOOGLE_API_KEY)
        store_name: Resource name of the File Search store (e.g., projects/.../locations/.../collections/.../dataStores/...)
        model: Model to use for retrieval (default: gemini-1.5-flash)
    """

    def __init__(self, config: dict):
        super().__init__(config)

        self.api_key = config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ConfigError(
                "Missing required field: api_key (or GOOGLE_API_KEY env var)"
            )

        self.store_name = config.get("store_name")
        # Allow store_name to be optional if we want to support dynamic creation later,
        # but for now, let's require it as per the plan.
        if not self.store_name:
            raise ConfigError("Missing required field: store_name")

        self.model_name = config.get(
            "model", "gemini-1.5-flash-lite"
        )  # Updated default

        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            raise ConfigError(f"Failed to initialize Google GenAI client: {str(e)}")

    def search(self, query: str, top_k: int = 5) -> SearchResult:
        """
        Execute search using Google File Search.

        Note: The Google File Search API is primarily a generation API with grounding.
        We use generate_content with the file_search tool and extract the grounding metadata.
        top_k is not directly supported by the API in the same way as vector DBs,
        but we can try to influence it or just take what we get.
        """
        try:
            # Determine top_k: prefer config, then argument
            config_top_k = self.config.get("top_k")
            final_top_k = int(config_top_k) if config_top_k is not None else top_k

            # Configure the tool with the specific store
            tool = types.Tool(
                file_search=types.FileSearch(
                    file_search_store_names=[self.store_name], top_k=final_top_k
                )
            )

            # Generate content to get grounding metadata
            # We wrap the query in a prompt to encourage concise answers        # Create prompt
            prompt = f"Question: {query}"

            # Execute search
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[tool],
                    # We might want to set temperature to 0 for more deterministic retrieval behavior
                    temperature=0.0,
                ),
            )

            chunks: List[RetrievedChunk] = []
            seen_contents = set()
            total_tokens_returned = 0

            # Extract chunks directly from grounding chunks (the actual retrieved content)
            if response.candidates and response.candidates[0].grounding_metadata:
                md = response.candidates[0].grounding_metadata

                if md.grounding_chunks:
                    for g_chunk in md.grounding_chunks:
                        rc = g_chunk.retrieved_context
                        if rc and rc.text:
                            # Deduplicate based on content
                            if rc.text in seen_contents:
                                continue
                            seen_contents.add(rc.text)

                            chunk_token_count = count_tokens(self.model_name, rc.text)
                            total_tokens_returned += chunk_token_count

                            chunks.append(
                                RetrievedChunk(
                                    content=rc.text,
                                    score=None,  # Grounding chunks don't have individual scores in the API response
                                    token_count=chunk_token_count,
                                    metadata={
                                        "uri": rc.uri,
                                        "title": rc.title,
                                        "source": rc.title or "google-file-search",
                                        "citations": f"{rc.title} ({rc.uri})" if rc.title and rc.uri else rc.uri or rc.title or "",
                                    },
                                )
                            )

            # Fallback: if no chunks found but we have text, return the text as a single chunk
            # This handles cases where grounding might fail but the model answers anyway
            if not chunks and response.text:
                chunk_token_count = count_tokens(self.model_name, response.text)
                total_tokens_returned += chunk_token_count
                chunks.append(
                    RetrievedChunk(
                        content=response.text,
                        score=1.0,
                        token_count=chunk_token_count,
                        metadata={
                            "source": "google-file-search",
                            "note": "Fallback to generated text (no grounding chunks found)",
                        },
                    )
                )

            # Calculate cost
            metadata = {}
            cost = None
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count

                metadata["input_tokens"] = input_tokens
                metadata["output_tokens"] = output_tokens
                metadata["total_tokens"] = (
                    response.usage_metadata.total_token_count
                )  # This is for the LLM call, not the retrieved chunks

                cost = calculate_llm_cost(self.model_name, input_tokens, output_tokens)

            return SearchResult(
                chunks=chunks,
                metadata=metadata,
                cost=cost,
                total_tokens_returned=total_tokens_returned,
            )

        except Exception as e:
            raise RunError(f"Google File Search failed: {str(e)}")


# Register the tool
from .registry import register_tool

register_tool("google_file_search", GoogleFileSearchProvider)
