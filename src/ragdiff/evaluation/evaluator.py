"""LLM-based evaluation using Claude for qualitative comparison."""

import logging
import os
import time
from typing import Optional

from anthropic import Anthropic

from ..core.models import ComparisonResult, LLMEvaluation

logger = logging.getLogger(__name__)


class LLMEvaluator:
    """Uses Claude to provide qualitative evaluation of RAG results.

    Thread-Safety:
        This class is safe for concurrent use. Each instance maintains its own
        Anthropic client and evaluation state. The DISPLAY_NAMES class variable
        is read-only and should never be modified after class definition.
    """

    # Map internal tool names to display names (if needed)
    # Empty dict means tool names are used as-is
    #
    # WARNING: READ-ONLY - Do not modify this dict after class definition.
    # Modification would affect all instances across all threads and could
    # cause race conditions. If you need custom display names, pass them
    # to the constructor or use a subclass.
    DISPLAY_NAMES: dict[str, str] = {}

    def __init__(
        self, model: str = "claude-sonnet-4-20250514", api_key: Optional[str] = None
    ):
        """Initialize LLM evaluator.

        Args:
            model: Claude model to use for evaluation
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = Anthropic(api_key=self.api_key)
        logger.info(f"LLM Evaluator initialized with model: {model}")

    def evaluate(self, result: ComparisonResult) -> LLMEvaluation:
        """Evaluate comparison results using Claude.

        Args:
            result: ComparisonResult to evaluate

        Returns:
            LLMEvaluation with qualitative analysis
        """
        start_time = time.time()

        try:
            # Build evaluation prompt
            prompt = self._build_evaluation_prompt(result)

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            # Extract text from content blocks
            analysis_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    analysis_text = block.text
                    break
            evaluation = self._parse_evaluation(analysis_text, result)

            # Add metadata
            evaluation.evaluation_time_ms = (time.time() - start_time) * 1000
            evaluation.raw_response = analysis_text

            logger.info(f"Evaluation complete in {evaluation.evaluation_time_ms:.2f}ms")
            return evaluation

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Return a fallback evaluation
            return LLMEvaluation(
                llm_model=self.model,
                winner=None,
                analysis=f"Evaluation failed: {str(e)}",
                quality_scores={},
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

    def _build_evaluation_prompt(self, result: ComparisonResult) -> str:
        """Build prompt for Claude evaluation.

        Args:
            result: Comparison result

        Returns:
            Formatted prompt string
        """
        tool_names = list(result.tool_results.keys())

        # Map tool names to display names for the prompt
        display_names = [self.DISPLAY_NAMES.get(name, name) for name in tool_names]

        prompt_parts = [
            "You are an expert evaluator of RAG (Retrieval Augmented Generation) systems.",
            f"\nQuery: {result.query}",
            "\n\nI need you to compare the quality of results from different RAG systems.",
            "\n\n---RESULTS---\n",
        ]

        # Add results from each tool using display names
        for tool_name, results in result.tool_results.items():
            display_name = self.DISPLAY_NAMES.get(tool_name, tool_name)
            prompt_parts.append(f"\n## {display_name.upper()} Results:\n")
            if not results:
                prompt_parts.append("(No results returned)\n")
            else:
                for idx, res in enumerate(results[:5], 1):  # Limit to top 5
                    prompt_parts.append(
                        f"\n{idx}. [Score: {res.score:.3f}] [{res.source}]\n"
                    )
                    prompt_parts.append(f"{res.text}\n")

        # Add evaluation criteria with display names
        prompt_parts.extend(
            [
                "\n---EVALUATION TASK---",
                "\nCompare these results on the following dimensions:",
                "1. **Relevance**: How well do results match the query intent?",
                "2. **Completeness**: How comprehensive is the information?",
                "3. **Accuracy**: Are the results factually correct (where verifiable)?",
                "4. **Coherence**: Is the text clear and well-structured?",
                "5. **Source Quality**: Are sources credible and authoritative?",
                "\nProvide your analysis in this format:",
                "\nWINNER: [tool_name or 'TIE']",
                f"\nQUALITY SCORES (0-100): {', '.join(f'{name}=X' for name in display_names)}",
                "\nIMPORTANT: Quality scores MUST be on a 0-100 scale where 0=completely irrelevant and 100=perfect results.",
                "\nANALYSIS:",
                "• Relevance: [comparison]",
                "• Completeness: [comparison]",
                "• Accuracy: [comparison]",
                "• Coherence: [comparison]",
                "• Source Quality: [comparison]",
                "\nKEY DIFFERENCES:",
                "• [difference 1]",
                "• [difference 2]",
                "\nRECOMMENDATION: [your recommendation]",
            ]
        )

        return "".join(prompt_parts)

    def _parse_evaluation(
        self, analysis_text: str, result: ComparisonResult
    ) -> LLMEvaluation:
        """Parse Claude's response into structured evaluation.

        Args:
            analysis_text: Raw text from Claude
            result: Original comparison result

        Returns:
            Structured LLMEvaluation
        """
        tool_names = list(result.tool_results.keys())

        # Create reverse mapping: display_name -> internal_name
        reverse_mapping = {v.lower(): k for k, v in self.DISPLAY_NAMES.items()}

        # Parse winner
        winner = None
        if "WINNER:" in analysis_text:
            winner_line = [
                line
                for line in analysis_text.split("\n")
                if line.strip().startswith("WINNER:")
            ]
            if winner_line:
                winner_text = winner_line[0].split(":", 1)[1].strip().lower()
                if winner_text != "tie":
                    # Try to match display name first, then internal name
                    if winner_text in reverse_mapping:
                        winner = reverse_mapping[winner_text]
                    else:
                        # Fallback to matching internal tool name
                        for name in tool_names:
                            if name.lower() in winner_text:
                                winner = name
                                break

        # Parse quality scores
        quality_scores = {}
        if "QUALITY SCORES" in analysis_text:
            score_line = [
                line for line in analysis_text.split("\n") if "QUALITY SCORES" in line
            ]
            if score_line:
                # Extract scores like "vectara=78" or "goodmem: 65"
                score_text = (
                    score_line[0].split(":", 1)[1] if ":" in score_line[0] else ""
                )
                for tool_name in tool_names:
                    display_name = self.DISPLAY_NAMES.get(tool_name, tool_name)
                    for part in score_text.split(","):
                        part_lower = part.lower()
                        # Check for both display name and internal name
                        if (
                            display_name.lower() in part_lower
                            or tool_name.lower() in part_lower
                        ):
                            try:
                                score = int("".join(c for c in part if c.isdigit()))
                                quality_scores[tool_name] = score
                                break
                            except ValueError:
                                pass

        return LLMEvaluation(
            llm_model=self.model,
            winner=winner,
            analysis=analysis_text,
            quality_scores=quality_scores,
        )
