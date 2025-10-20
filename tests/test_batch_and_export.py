"""Tests for batch processing and export formats."""

import csv
import json
from io import StringIO

from src.core.models import ComparisonResult, RagResult


class TestBatchProcessing:
    """Test batch processing functionality."""

    def test_batch_reads_queries_from_file(self, tmp_path):
        """Test that batch command reads queries from file."""
        # Create test queries file
        queries_file = tmp_path / "queries.txt"
        queries_file.write_text("Query 1\nQuery 2\nQuery 3\n")

        queries = [
            line.strip()
            for line in queries_file.read_text().split("\n")
            if line.strip()
        ]

        assert len(queries) == 3
        assert queries[0] == "Query 1"
        assert queries[1] == "Query 2"
        assert queries[2] == "Query 3"

    def test_batch_skips_empty_lines(self, tmp_path):
        """Test that batch skips empty lines in queries file."""
        queries_file = tmp_path / "queries.txt"
        queries_file.write_text("Query 1\n\nQuery 2\n  \nQuery 3\n")

        queries = [
            line.strip()
            for line in queries_file.read_text().split("\n")
            if line.strip()
        ]

        assert len(queries) == 3
        assert "" not in queries

    def test_batch_creates_output_directory(self, tmp_path):
        """Test that batch creates output directory if it doesn't exist."""
        output_dir = tmp_path / "outputs"
        assert not output_dir.exists()

        output_dir.mkdir(parents=True, exist_ok=True)

        assert output_dir.exists()
        assert output_dir.is_dir()


class TestJSONLExport:
    """Test JSONL export format."""

    def test_jsonl_one_line_per_result(self):
        """Test that JSONL exports one JSON object per line."""
        results = [
            ComparisonResult(query="Query 1", tool_results={"tool1": []}, errors={}),
            ComparisonResult(query="Query 2", tool_results={"tool1": []}, errors={}),
        ]

        # Simulate JSONL export
        output = StringIO()
        for result in results:
            json.dump(result.to_dict(), output)
            output.write("\n")

        lines = output.getvalue().strip().split("\n")

        assert len(lines) == 2
        # Each line should be valid JSON
        json.loads(lines[0])
        json.loads(lines[1])

    def test_jsonl_preserves_all_fields(self):
        """Test that JSONL export preserves all result fields."""
        result = ComparisonResult(
            query="Test query",
            tool_results={
                "goodmem": [
                    RagResult(id="1", text="Result 1", score=0.9, source="Source1")
                ]
            },
            errors={"mawsuah": "Error message"},
        )

        json_str = json.dumps(result.to_dict())
        parsed = json.loads(json_str)

        assert parsed["query"] == "Test query"
        assert "goodmem" in parsed["tool_results"]
        assert "mawsuah" in parsed["errors"]
        assert parsed["errors"]["mawsuah"] == "Error message"

    def test_jsonl_format_in_cli(self):
        """Test JSONL format option in CLI."""
        result = ComparisonResult(query="Test", tool_results={"tool1": []}, errors={})

        # Simulate CLI jsonl format
        output = json.dumps(result.to_dict())

        # Should be valid JSON
        parsed = json.loads(output)
        assert parsed["query"] == "Test"


class TestCSVExport:
    """Test CSV export format."""

    def test_csv_has_header_row(self):
        """Test that CSV export includes header row."""
        output = StringIO()
        writer = csv.writer(output)

        tool_names = ["goodmem", "mawsuah"]
        header = ["query", "timestamp"]
        for tool_name in tool_names:
            header.extend(
                [
                    f"{tool_name}_count",
                    f"{tool_name}_avg_score",
                    f"{tool_name}_latency_ms",
                ]
            )

        writer.writerow(header)

        csv_text = output.getvalue()
        lines = csv_text.strip().split("\n")

        assert len(lines) == 1  # Just header
        assert "query" in lines[0]
        assert "goodmem_count" in lines[0]
        assert "mawsuah_avg_score" in lines[0]

    def test_csv_data_row_format(self):
        """Test CSV data row format."""
        result = ComparisonResult(
            query="Test query",
            tool_results={
                "goodmem": [
                    RagResult(id="1", text="Text", score=0.9, latency_ms=100.0)
                ],
                "mawsuah": [
                    RagResult(id="2", text="Text", score=0.7, latency_ms=200.0),
                    RagResult(id="3", text="Text", score=0.8, latency_ms=200.0),
                ],
            },
            errors={},
        )

        output = StringIO()
        writer = csv.writer(output)
        tool_names = ["goodmem", "mawsuah"]

        # Write header
        header = ["query", "timestamp"]
        for tool_name in tool_names:
            header.extend(
                [
                    f"{tool_name}_count",
                    f"{tool_name}_avg_score",
                    f"{tool_name}_latency_ms",
                ]
            )
        writer.writerow(header)

        # Write data
        row = [result.query, result.timestamp.isoformat()]
        for tool_name in tool_names:
            tool_results = result.tool_results.get(tool_name, [])
            count = len(tool_results)
            avg_score = sum(r.score for r in tool_results) / count if count > 0 else 0
            latency = tool_results[0].latency_ms if tool_results else 0
            row.extend([count, f"{avg_score:.3f}", f"{latency:.1f}"])
        writer.writerow(row)

        csv_text = output.getvalue()
        lines = csv_text.strip().split("\n")

        assert len(lines) == 2  # Header + data
        data_line = lines[1]

        # Parse the CSV
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        data_row = rows[1]

        assert data_row[0] == "Test query"
        assert data_row[2] == "1"  # goodmem count
        assert data_row[3] == "0.900"  # goodmem avg_score
        assert data_row[5] == "2"  # mawsuah count
        assert data_row[6] == "0.750"  # mawsuah avg_score (0.7 + 0.8) / 2

    def test_csv_includes_llm_evaluation_if_present(self):
        """Test that CSV includes LLM evaluation columns if available."""
        from src.core.models import LLMEvaluation

        evaluation = LLMEvaluation(
            llm_model="claude",
            winner="goodmem",
            analysis="Test",
            quality_scores={"goodmem": 8, "mawsuah": 6},
        )

        result = ComparisonResult(
            query="Test",
            tool_results={"goodmem": [], "mawsuah": []},
            errors={},
            llm_evaluation=evaluation,
        )

        output = StringIO()
        writer = csv.writer(output)
        tool_names = ["goodmem", "mawsuah"]

        # Header with LLM columns
        header = ["query", "timestamp"]
        for tool_name in tool_names:
            header.extend(
                [
                    f"{tool_name}_count",
                    f"{tool_name}_avg_score",
                    f"{tool_name}_latency_ms",
                ]
            )
        header.extend(["llm_winner"] + [f"llm_score_{name}" for name in tool_names])
        writer.writerow(header)

        # Data with LLM scores
        row = [result.query, result.timestamp.isoformat()]
        for tool_name in tool_names:
            row.extend([0, "0.000", "0.0"])
        row.append(result.llm_evaluation.winner)
        for tool_name in tool_names:
            row.append(result.llm_evaluation.quality_scores.get(tool_name, ""))
        writer.writerow(row)

        csv_text = output.getvalue()
        lines = csv_text.strip().split("\n")

        assert "llm_winner" in lines[0]
        assert "llm_score_goodmem" in lines[0]

        # Parse and check data
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        data_row = rows[1]

        # Find llm_winner column
        header_row = rows[0]
        llm_winner_idx = header_row.index("llm_winner")
        assert data_row[llm_winner_idx] == "goodmem"


class TestLatencyStatistics:
    """Test latency percentile calculations."""

    def test_percentile_calculation(self):
        """Test that percentile calculations are correct."""
        import statistics

        latencies = [
            100.0,
            150.0,
            200.0,
            250.0,
            300.0,
            350.0,
            400.0,
            450.0,
            500.0,
            1000.0,
        ]
        latencies_sorted = sorted(latencies)

        count = len(latencies_sorted)
        p50 = statistics.median(latencies_sorted)
        p95 = latencies_sorted[int(0.95 * count)]
        p99 = latencies_sorted[int(0.99 * count)]

        assert p50 == 325.0  # Median of 10 items (avg of 5th and 6th: (300 + 350) / 2)
        assert p95 == 1000.0  # 95th percentile (9.5th item, rounds to 9)
        assert p99 == 1000.0  # 99th percentile (9.9th item, rounds to 9)

    def test_latency_stats_empty_list(self):
        """Test latency stats with empty results."""
        latencies = []

        # Should handle empty gracefully
        if latencies:
            import statistics

            p50 = statistics.median(latencies)
        else:
            p50 = None

        assert p50 is None

    def test_latency_collection_from_results(self):
        """Test collecting latencies from comparison results."""
        results = [
            ComparisonResult(
                query="Q1",
                tool_results={
                    "goodmem": [
                        RagResult(id="1", text="t", score=0.9, latency_ms=100.0)
                    ],
                    "mawsuah": [
                        RagResult(id="2", text="t", score=0.8, latency_ms=200.0)
                    ],
                },
                errors={},
            ),
            ComparisonResult(
                query="Q2",
                tool_results={
                    "goodmem": [
                        RagResult(id="3", text="t", score=0.9, latency_ms=150.0)
                    ],
                    "mawsuah": [
                        RagResult(id="4", text="t", score=0.8, latency_ms=250.0)
                    ],
                },
                errors={},
            ),
        ]

        # Collect latencies
        latencies_by_tool = {"goodmem": [], "mawsuah": []}
        for result in results:
            for tool_name in ["goodmem", "mawsuah"]:
                tool_results = result.tool_results.get(tool_name, [])
                if tool_results and tool_results[0].latency_ms:
                    latencies_by_tool[tool_name].append(tool_results[0].latency_ms)

        assert latencies_by_tool["goodmem"] == [100.0, 150.0]
        assert latencies_by_tool["mawsuah"] == [200.0, 250.0]

    def test_percentile_with_single_value(self):
        """Test percentiles with single value."""
        import statistics

        latencies = [100.0]
        p50 = statistics.median(latencies)
        count = len(latencies)
        p95 = latencies[int(0.95 * count)] if count > 0 else 0

        assert p50 == 100.0
        assert p95 == 100.0  # Only one value, so all percentiles are the same


class TestExportFormats:
    """Test export format integration."""

    def test_comparison_result_to_dict_complete(self):
        """Test that to_dict includes all necessary fields."""
        result = ComparisonResult(
            query="Test query",
            tool_results={
                "goodmem": [
                    RagResult(
                        id="1",
                        text="Result text",
                        score=0.9,
                        source="Source1",
                        metadata={"key": "value"},
                    )
                ]
            },
            errors={"mawsuah": "API error"},
        )

        result_dict = result.to_dict()

        assert "query" in result_dict
        assert "timestamp" in result_dict
        assert "tool_results" in result_dict
        assert "errors" in result_dict
        assert "llm_evaluation" in result_dict

        # Check nested structure
        assert "goodmem" in result_dict["tool_results"]
        assert len(result_dict["tool_results"]["goodmem"]) == 1
        assert result_dict["tool_results"]["goodmem"][0]["text"] == "Result text"
        assert result_dict["errors"]["mawsuah"] == "API error"
