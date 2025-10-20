"""Tests for LLM evaluation functionality."""

from unittest.mock import Mock, patch

import pytest

from src.core.models import ComparisonResult, LLMEvaluation, RagResult
from src.evaluation.evaluator import LLMEvaluator


class TestLLMEvaluator:
    """Test LLM evaluation functionality."""

    def test_evaluator_requires_api_key(self):
        """Test that evaluator raises error if no API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                LLMEvaluator()

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluator_initializes_with_api_key(self, mock_anthropic):
        """Test that evaluator initializes correctly with API key."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator(model="claude-sonnet-4-20250514")

            assert evaluator.model == "claude-sonnet-4-20250514"
            assert evaluator.api_key == "test-key"
            mock_anthropic.assert_called_once_with(api_key="test-key")

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_calls_anthropic_api(self, mock_anthropic):
        """Test that evaluate calls Anthropic API with proper prompt."""
        # Mock Anthropic client
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        # Mock response
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text="WINNER: goodmem\nQUALITY SCORES: goodmem=8, mawsuah=6\nANALYSIS: Goodmem results are more relevant."
            )
        ]
        mock_client.messages.create.return_value = mock_response

        # Create test comparison result
        result = ComparisonResult(
            query="test query",
            tool_results={
                "goodmem": [
                    RagResult(id="1", text="Good result", score=0.9, source="Source1")
                ],
                "mawsuah": [
                    RagResult(id="2", text="OK result", score=0.7, source="Source2")
                ],
            },
            errors={},
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator()
            evaluation = evaluator.evaluate(result)

            # Verify API was called
            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args.kwargs

            # Check parameters
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"
            assert call_kwargs["max_tokens"] == 4096
            assert call_kwargs["temperature"] == 0.1

            # Check prompt includes query and results
            prompt = call_kwargs["messages"][0]["content"]
            assert "test query" in prompt
            assert "Good result" in prompt
            assert "OK result" in prompt

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_parses_winner_correctly(self, mock_anthropic):
        """Test that evaluate correctly parses winner from response."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        # Test different winner formats
        test_cases = [
            ("WINNER: goodmem", "goodmem"),
            ("WINNER: mawsuah", "mawsuah"),
            ("WINNER: tie", None),
            ("WINNER: Goodmem performs better", "goodmem"),
        ]

        for response_text, expected_winner in test_cases:
            mock_response = Mock()
            mock_response.content = [Mock(text=response_text)]
            mock_client.messages.create.return_value = mock_response

            result = ComparisonResult(
                query="test", tool_results={"goodmem": [], "mawsuah": []}, errors={}
            )

            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                evaluator = LLMEvaluator()
                evaluation = evaluator.evaluate(result)

                assert evaluation.winner == expected_winner

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_parses_quality_scores(self, mock_anthropic):
        """Test that evaluate correctly parses quality scores."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [
            Mock(text="QUALITY SCORES (0-10): goodmem=8, mawsuah=6")
        ]
        mock_client.messages.create.return_value = mock_response

        result = ComparisonResult(
            query="test", tool_results={"goodmem": [], "mawsuah": []}, errors={}
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator()
            evaluation = evaluator.evaluate(result)

            assert evaluation.quality_scores == {"goodmem": 8, "mawsuah": 6}

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_handles_api_failure(self, mock_anthropic):
        """Test that evaluate handles API failures gracefully."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API Error")

        result = ComparisonResult(
            query="test", tool_results={"goodmem": [], "mawsuah": []}, errors={}
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator()
            evaluation = evaluator.evaluate(result)

            # Should return fallback evaluation
            assert evaluation.winner is None
            assert "failed" in evaluation.analysis.lower()
            assert evaluation.evaluation_time_ms is not None

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_tracks_timing(self, mock_anthropic):
        """Test that evaluate tracks evaluation time."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        mock_response = Mock()
        mock_response.content = [Mock(text="WINNER: goodmem")]
        mock_client.messages.create.return_value = mock_response

        result = ComparisonResult(
            query="test", tool_results={"goodmem": [], "mawsuah": []}, errors={}
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator()
            evaluation = evaluator.evaluate(result)

            # Should have timing information
            assert evaluation.evaluation_time_ms is not None
            assert evaluation.evaluation_time_ms > 0

    @patch("src.evaluation.evaluator.Anthropic")
    def test_evaluate_includes_raw_response(self, mock_anthropic):
        """Test that evaluate includes raw response in evaluation."""
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        response_text = "WINNER: goodmem\nANALYSIS: Detailed analysis here"
        mock_response = Mock()
        mock_response.content = [Mock(text=response_text)]
        mock_client.messages.create.return_value = mock_response

        result = ComparisonResult(
            query="test", tool_results={"goodmem": [], "mawsuah": []}, errors={}
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            evaluator = LLMEvaluator()
            evaluation = evaluator.evaluate(result)

            assert evaluation.raw_response == response_text
            assert evaluation.analysis == response_text


class TestLLMEvaluation:
    """Test LLMEvaluation data model."""

    def test_llm_evaluation_to_dict(self):
        """Test that LLMEvaluation converts to dict correctly."""
        evaluation = LLMEvaluation(
            llm_model="claude-sonnet-4",
            winner="goodmem",
            analysis="Analysis text",
            quality_scores={"goodmem": 8, "mawsuah": 6},
            evaluation_time_ms=1234.5,
        )

        result = evaluation.to_dict()

        assert result["llm_model"] == "claude-sonnet-4"
        assert result["winner"] == "goodmem"
        assert result["analysis"] == "Analysis text"
        assert result["quality_scores"] == {"goodmem": 8, "mawsuah": 6}
        assert result["evaluation_time_ms"] == 1234.5

    def test_comparison_result_includes_llm_evaluation(self):
        """Test that ComparisonResult can include LLM evaluation."""
        evaluation = LLMEvaluation(
            llm_model="claude-sonnet-4",
            winner="goodmem",
            analysis="Test analysis",
            quality_scores={},
        )

        result = ComparisonResult(
            query="test",
            tool_results={"goodmem": []},
            errors={},
            llm_evaluation=evaluation,
        )

        assert result.llm_evaluation is not None
        assert result.llm_evaluation.winner == "goodmem"

    def test_comparison_result_to_dict_with_evaluation(self):
        """Test that ComparisonResult.to_dict includes evaluation."""
        evaluation = LLMEvaluation(
            llm_model="claude-sonnet-4",
            winner="goodmem",
            analysis="Test",
            quality_scores={},
        )

        result = ComparisonResult(
            query="test",
            tool_results={"goodmem": []},
            errors={},
            llm_evaluation=evaluation,
        )

        result_dict = result.to_dict()

        assert result_dict["llm_evaluation"] is not None
        assert result_dict["llm_evaluation"]["winner"] == "goodmem"
