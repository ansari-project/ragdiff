"""Response mapping engine for OpenAPI adapter using JMESPath."""

import logging
import re
from typing import Any

import jmespath

from ..core.errors import ConfigurationError
from ..core.models import RagResult

logger = logging.getLogger(__name__)


class TemplateEngine:
    """Handle template variable substitution in requests.

    Supports ${var} syntax for variable substitution in:
    - Request bodies (JSON)
    - Query parameters
    - Headers

    Example:
        engine = TemplateEngine()
        template = {"query": "${query}", "limit": "${top_k}"}
        variables = {"query": "test", "top_k": 5}
        result = engine.render(template, variables)
        # result: {"query": "test", "limit": 5}
    """

    # Pattern to match ${variable_name}
    VARIABLE_PATTERN = re.compile(r"\$\{(\w+)\}")

    def render(self, template: Any, variables: dict[str, Any]) -> Any:
        """Render template with variable substitution.

        Args:
            template: Template data (dict, list, string, or primitive)
            variables: Variables to substitute

        Returns:
            Rendered data with variables substituted
        """
        if isinstance(template, str):
            return self._render_string(template, variables)
        elif isinstance(template, dict):
            return {k: self.render(v, variables) for k, v in template.items()}
        elif isinstance(template, list):
            return [self.render(item, variables) for item in template]
        else:
            # Primitive types (int, float, bool, None) pass through
            return template

    def _render_string(self, template: str, variables: dict[str, Any]) -> Any:
        """Render a string template.

        Args:
            template: Template string (e.g., "${query}" or "prefix-${var}")
            variables: Variables to substitute

        Returns:
            Rendered value (string or original type if fully substituted)
        """
        # Find all ${var} patterns
        matches = list(self.VARIABLE_PATTERN.finditer(template))

        if not matches:
            return template

        # If template is exactly "${var}", return the variable's value directly
        # This preserves type (e.g., ${top_k} returns int 5, not string "5")
        if len(matches) == 1 and matches[0].group(0) == template:
            var_name = matches[0].group(1)
            if var_name in variables:
                return variables[var_name]
            else:
                raise ConfigurationError(
                    f"Template variable '${{{var_name}}}' not provided"
                )

        # Otherwise, do string substitution
        result = template
        for match in matches:
            var_name = match.group(1)
            if var_name in variables:
                # Convert to string for substitution
                result = result.replace(match.group(0), str(variables[var_name]))
            else:
                raise ConfigurationError(
                    f"Template variable '${{{var_name}}}' not provided"
                )

        return result


class ResponseMapper:
    """Map API responses to RagResult using JMESPath expressions.

    Extracts fields from arbitrary JSON responses using JMESPath,
    a powerful query language for JSON (used by AWS CLI, Azure CLI).

    Example config:
        {
            "results_array": "data.results",
            "fields": {
                "id": "id",
                "text": "content.text",
                "score": "relevance_score",
                "source": "source.name",
                "metadata": "{author: metadata.author, date: published}"
            }
        }
    """

    def __init__(self, mapping_config: dict[str, Any]):
        """Initialize response mapper with JMESPath configuration.

        Args:
            mapping_config: Mapping configuration dict with:
                - results_array: JMESPath to array of results
                - fields: Dict of field mappings (id, text, score, etc.)

        Raises:
            ConfigurationError: If mapping config is invalid
        """
        self.mapping_config = mapping_config

        # Validate required fields
        if "results_array" not in mapping_config:
            raise ConfigurationError("Missing 'results_array' in response_mapping")
        if "fields" not in mapping_config:
            raise ConfigurationError("Missing 'fields' in response_mapping")

        # Compile JMESPath expressions for efficiency
        self.results_array_expr = jmespath.compile(mapping_config["results_array"])

        self.field_exprs = {}
        for field_name, jmespath_str in mapping_config["fields"].items():
            try:
                self.field_exprs[field_name] = jmespath.compile(jmespath_str)
            except Exception as e:
                raise ConfigurationError(
                    f"Invalid JMESPath for field '{field_name}': {jmespath_str}. Error: {e}"
                ) from e

    def map_results(self, response: dict) -> list[RagResult]:
        """Extract RagResult objects from API response.

        Args:
            response: Raw JSON response from API

        Returns:
            List of RagResult objects

        Raises:
            ConfigurationError: If mapping fails
        """
        # Extract results array
        try:
            results_array = self.results_array_expr.search(response)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to extract results array using JMESPath '{self.mapping_config['results_array']}': {e}"
            ) from e

        if results_array is None:
            logger.warning(
                f"Results array not found using path '{self.mapping_config['results_array']}'"
            )
            return []

        if not isinstance(results_array, list):
            raise ConfigurationError(
                f"Results array is not a list: got {type(results_array).__name__}"
            )

        # Map each result item to RagResult
        rag_results = []
        for idx, item in enumerate(results_array):
            try:
                rag_result = self._map_item(item, idx)
                rag_results.append(rag_result)
            except Exception as e:
                logger.warning(f"Failed to map result item {idx}: {e}")
                continue

        return rag_results

    def _map_item(self, item: dict, index: int) -> RagResult:
        """Map a single result item to RagResult.

        Args:
            item: Single result item from API response
            index: Index of item (for error messages)

        Returns:
            RagResult object

        Raises:
            ConfigurationError: If required fields are missing
        """
        # Extract required fields
        id_value = self._extract_field(item, "id", required=True, index=index)
        text_value = self._extract_field(item, "text", required=True, index=index)
        score_value = self._extract_field(item, "score", required=True, index=index)

        # Extract optional fields
        source_value = self._extract_field(item, "source", required=False, index=index)
        metadata_value = self._extract_field(
            item, "metadata", required=False, index=index
        )

        # Normalize score to 0-1 range
        score_normalized = self._normalize_score(score_value)

        return RagResult(
            id=str(id_value),
            text=str(text_value),
            score=score_normalized,
            source=str(source_value) if source_value is not None else None,
            metadata=metadata_value if isinstance(metadata_value, dict) else None,
        )

    def _extract_field(
        self, item: dict, field_name: str, required: bool, index: int
    ) -> Any:
        """Extract a field from result item using JMESPath.

        Args:
            item: Result item dict
            field_name: Field name (id, text, score, source, metadata)
            required: Whether field is required
            index: Item index (for error messages)

        Returns:
            Extracted value or None

        Raises:
            ConfigurationError: If required field is missing or extraction fails
        """
        if field_name not in self.field_exprs:
            if required:
                raise ConfigurationError(
                    f"Required field '{field_name}' not in mapping configuration"
                )
            return None

        try:
            value = self.field_exprs[field_name].search(item)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to extract field '{field_name}' from item {index}: {e}"
            ) from e

        if value is None and required:
            raise ConfigurationError(
                f"Required field '{field_name}' is None in item {index}. "
                f"JMESPath: {self.mapping_config['fields'][field_name]}"
            )

        return value

    def _normalize_score(self, score: Any) -> float:
        """Normalize score to 0-1 range.

        Handles various score formats:
        - Already 0-1: pass through
        - 0-100: divide by 100
        - 0-1000: divide by 1000
        - Negative: clamp to 0

        Args:
            score: Raw score value

        Returns:
            Normalized score (0-1)

        Raises:
            ConfigurationError: If score is not numeric
        """
        try:
            score_float = float(score)
        except (TypeError, ValueError) as e:
            raise ConfigurationError(f"Score is not numeric: {score}") from e

        # Normalize based on range
        if 0 <= score_float <= 1:
            return score_float
        elif score_float > 100:
            # Assume 0-1000 scale
            return min(score_float / 1000.0, 1.0)
        elif score_float > 1:
            # Assume 0-100 scale
            return min(score_float / 100.0, 1.0)
        else:
            # Negative scores -> clamp to 0
            logger.warning(f"Negative score {score_float} clamped to 0")
            return 0.0
