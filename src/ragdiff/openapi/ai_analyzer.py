"""AI-powered analysis for OpenAPI provider generation.

Uses LiteLLM to analyze OpenAPI specifications and API responses,
automatically identifying search endpoints and generating JMESPath mappings.
"""

import json
import logging
from typing import Any

from litellm import completion

from ..core.errors import ConfigurationError
from .models import EndpointInfo

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI-powered analyzer for OpenAPI specs and API responses.

    Uses LiteLLM to call any LLM (Claude, GPT, etc.) for:
    - Identifying which endpoint is the search/query endpoint
    - Generating JMESPath mappings from example API responses

    LiteLLM automatically reads API keys from environment:
    - ANTHROPIC_API_KEY for Claude models
    - OPENAI_API_KEY for GPT models
    - etc.
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize AI analyzer.

        Args:
            model: LiteLLM model identifier (e.g., "claude-3-5-sonnet-20241022",
                   "gpt-4", "gpt-3.5-turbo", etc.)
        """
        self.model = model
        logger.info(f"AI Analyzer initialized with model: {model}")

    def identify_search_endpoint(
        self, endpoints: list[EndpointInfo]
    ) -> tuple[str, str, str]:
        """Identify which endpoint is most likely the search/query endpoint.

        Args:
            endpoints: List of endpoints from OpenAPI spec

        Returns:
            Tuple of (path, method, reasoning)

        Raises:
            ConfigurationError: If AI cannot identify endpoint or returns invalid response
        """
        if not endpoints:
            raise ConfigurationError("No endpoints provided for analysis")

        logger.info(f"Analyzing {len(endpoints)} endpoints to identify search endpoint")

        # Build endpoint list for AI
        endpoint_descriptions = []
        for ep in endpoints:
            desc = f"- {ep.method} {ep.path}"
            if ep.summary:
                desc += f": {ep.summary}"
            if ep.description:
                desc += (
                    f" ({ep.description[:100]}...)"
                    if len(ep.description) > 100
                    else f" ({ep.description})"
                )
            endpoint_descriptions.append(desc)

        prompt = self._build_endpoint_identification_prompt(endpoint_descriptions)

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )

            # Extract response content
            content = response.choices[0].message.content
            logger.debug(f"AI response for endpoint identification: {content}")

            # Parse JSON response
            result = json.loads(content)

            path = result.get("path")
            method = result.get("method")
            reasoning = result.get("reasoning", "")

            if not path or not method:
                raise ConfigurationError(
                    "AI response missing required fields 'path' or 'method'"
                )

            logger.info(f"AI identified endpoint: {method} {path}")
            return path, method.upper(), reasoning

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Failed to parse AI response as JSON: {e}\nResponse: {content}"
            ) from e
        except Exception as e:
            raise ConfigurationError(f"Failed to identify search endpoint: {e}") from e

    def generate_response_mapping(self, example_response: dict) -> dict[str, Any]:
        """Generate JMESPath mappings from example API response.

        Args:
            example_response: Example JSON response from API

        Returns:
            Dict with response_mapping configuration:
            {
                "results_array": "data.results",
                "fields": {
                    "id": "id",
                    "text": "content.text",
                    "score": "relevance_score",
                    "source": "source.name",
                    "metadata": "{...}"
                }
            }

        Raises:
            ConfigurationError: If AI cannot generate mapping or returns invalid response
        """
        logger.info("Generating response mapping with AI")

        # Format response for readability
        response_json = json.dumps(example_response, indent=2)
        prompt = self._build_mapping_generation_prompt(response_json)

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000,
            )

            # Extract response content
            content = response.choices[0].message.content
            logger.debug(f"AI response for mapping generation: {content}")

            # Parse JSON response
            result = json.loads(content)

            # Validate structure
            if "results_array" not in result:
                raise ConfigurationError("AI response missing 'results_array' field")
            if "fields" not in result:
                raise ConfigurationError("AI response missing 'fields' field")

            fields = result["fields"]
            required_fields = ["id", "text", "score"]
            for field in required_fields:
                if field not in fields:
                    raise ConfigurationError(
                        f"AI response missing required field mapping: {field}"
                    )

            logger.info(
                f"AI generated mapping with results_array='{result['results_array']}'"
            )
            return result

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Failed to parse AI response as JSON: {e}\nResponse: {content}"
            ) from e
        except Exception as e:
            raise ConfigurationError(f"Failed to generate response mapping: {e}") from e

    def _build_endpoint_identification_prompt(
        self, endpoint_descriptions: list[str]
    ) -> str:
        """Build prompt for endpoint identification.

        Args:
            endpoint_descriptions: List of endpoint description strings

        Returns:
            Prompt string
        """
        endpoints_text = "\n".join(endpoint_descriptions)

        return f"""You are analyzing an OpenAPI specification to identify the search/query endpoint for a RAG (Retrieval-Augmented Generation) system.

Available endpoints:
{endpoints_text}

Identify which endpoint is most likely used for searching or querying documents. Look for endpoints with names, summaries, or descriptions containing words like: search, query, find, retrieve, lookup, etc.

Respond with JSON in this exact format:
{{
  "path": "/v1/search",
  "method": "POST",
  "reasoning": "Brief explanation of why you selected this endpoint"
}}

Important:
- Only respond with valid JSON, no additional text
- Use the exact path as shown in the list
- Method should be uppercase (GET, POST, etc.)
- If multiple search endpoints exist, choose the most general one
- If no obvious search endpoint exists, choose the most likely candidate
"""

    def _build_mapping_generation_prompt(self, response_json: str) -> str:
        """Build prompt for response mapping generation.

        Args:
            response_json: Formatted JSON response string

        Returns:
            Prompt string
        """
        return f"""You are analyzing an API response to generate JMESPath expressions for extracting search result fields.

Required fields to extract:
- id: Unique identifier (string)
- text: Main content text (string)
- score: Relevance score (float, ideally 0-1 range)
- source: Source document/name (string, optional)
- metadata: Additional metadata (dict, optional)

Example API response:
{response_json}

Generate JMESPath expressions to extract these fields. For the results_array, provide the path to the array of result items.

Respond with JSON in this exact format:
{{
  "results_array": "data.results",
  "fields": {{
    "id": "id",
    "text": "content.text",
    "score": "relevance_score",
    "source": "source.name",
    "metadata": "{{author: metadata.author, date: published_date}}"
  }}
}}

Important:
- Only respond with valid JSON, no additional text
- Use JMESPath syntax (not JSONPath or dotted notation)
- For metadata, construct a JMESPath object expression using {{key: path}} syntax
- If a field doesn't exist in the response, use a reasonable default path
- Ensure all paths are valid JMESPath expressions
- The results_array should point to an array of result objects
"""


# Example usage (for testing/documentation):
if __name__ == "__main__":
    # This would require ANTHROPIC_API_KEY or OPENAI_API_KEY in environment
    analyzer = AIAnalyzer()

    # Example endpoints
    endpoints = [
        EndpointInfo(
            path="/v1/search",
            method="POST",
            summary="Search documents",
            description="Full-text search across corpus",
        ),
        EndpointInfo(
            path="/v1/documents/{id}",
            method="GET",
            summary="Get document by ID",
        ),
    ]

    # Identify search endpoint
    path, method, reasoning = analyzer.identify_search_endpoint(endpoints)
    print(f"Identified: {method} {path}")
    print(f"Reasoning: {reasoning}")

    # Example response
    example_response = {
        "data": {
            "results": [
                {
                    "id": "doc-1",
                    "content": {"text": "The answer is..."},
                    "relevance_score": 0.95,
                    "source": {"name": "Source 1"},
                    "metadata": {"author": "Author 1"},
                }
            ]
        }
    }

    # Generate mapping
    mapping = analyzer.generate_response_mapping(example_response)
    print(f"Mapping: {json.dumps(mapping, indent=2)}")
