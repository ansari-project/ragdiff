"""Tests for thread-safe serialization utilities."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest

from ragdiff.core.models import ComparisonResult, RagResult
from ragdiff.core.serialization import (
    format_json_output,
    from_json,
    to_dict,
    to_json,
    to_serializable,
)


@dataclass
class SampleDataClass:
    """Sample dataclass for testing."""

    name: str
    count: int
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class TestToSerializable:
    """Test to_serializable function."""

    def test_none(self):
        """Test None serialization."""
        assert to_serializable(None) is None

    def test_primitives(self):
        """Test primitive types."""
        assert to_serializable("test") == "test"
        assert to_serializable(42) == 42
        assert to_serializable(3.14) == 3.14
        assert to_serializable(True) is True
        assert to_serializable(False) is False

    def test_datetime(self):
        """Test datetime serialization."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        result = to_serializable(dt)
        assert isinstance(result, str)
        assert "2025-01-15" in result
        assert "10:30:45" in result

    def test_dataclass(self):
        """Test dataclass serialization."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        obj = SampleDataClass(
            name="test", count=5, timestamp=dt, metadata={"key": "value"}
        )
        result = to_serializable(obj)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["count"] == 5
        assert isinstance(result["timestamp"], str)
        assert result["metadata"]["key"] == "value"

    def test_dict(self):
        """Test dictionary serialization."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        data = {"name": "test", "timestamp": dt, "nested": {"count": 5}}
        result = to_serializable(data)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert isinstance(result["timestamp"], str)
        assert result["nested"]["count"] == 5

    def test_list(self):
        """Test list serialization."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        data = ["test", 42, dt, {"key": "value"}]
        result = to_serializable(data)

        assert isinstance(result, list)
        assert len(result) == 4
        assert result[0] == "test"
        assert result[1] == 42
        assert isinstance(result[2], str)
        assert result[3]["key"] == "value"

    def test_nested_structures(self):
        """Test nested data structures."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        data = {
            "users": [
                {"name": "Alice", "created": dt},
                {"name": "Bob", "created": dt},
            ],
            "metadata": {"count": 2, "timestamp": dt},
        }
        result = to_serializable(data)

        assert isinstance(result["users"], list)
        assert len(result["users"]) == 2
        assert isinstance(result["users"][0]["created"], str)
        assert isinstance(result["metadata"]["timestamp"], str)

    def test_rag_result(self):
        """Test RagResult serialization."""
        result = RagResult(
            id="test-1",
            text="Test result",
            score=0.95,
            source="TestSource",
            metadata={"key": "value"},
        )
        serialized = to_serializable(result)

        assert isinstance(serialized, dict)
        assert serialized["id"] == "test-1"
        assert serialized["text"] == "Test result"
        assert serialized["score"] == 0.95
        assert serialized["source"] == "TestSource"

    def test_comparison_result(self):
        """Test ComparisonResult serialization."""
        result = ComparisonResult(
            query="test query",
            tool_results={
                "vectara": [
                    RagResult(id="1", text="Result 1", score=0.95),
                    RagResult(id="2", text="Result 2", score=0.85),
                ],
                "goodmem": [
                    RagResult(id="3", text="Result 3", score=0.90),
                ],
            },
            errors={},
        )
        serialized = to_serializable(result)

        assert isinstance(serialized, dict)
        assert serialized["query"] == "test query"
        assert "vectara" in serialized["tool_results"]
        assert len(serialized["tool_results"]["vectara"]) == 2


class TestToJson:
    """Test to_json function."""

    def test_simple_object(self):
        """Test JSON serialization of simple object."""
        data = {"name": "test", "count": 5}
        json_str = to_json(data, pretty=False)

        parsed = json.loads(json_str)
        assert parsed["name"] == "test"
        assert parsed["count"] == 5

    def test_pretty_printing(self):
        """Test pretty-printed JSON."""
        data = {"name": "test", "count": 5}
        json_str = to_json(data, pretty=True)

        assert "\n" in json_str  # Should have newlines
        assert "  " in json_str  # Should have indentation

    def test_dataclass_to_json(self):
        """Test dataclass to JSON."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        obj = SampleDataClass(name="test", count=5, timestamp=dt)
        json_str = to_json(obj, pretty=False)

        parsed = json.loads(json_str)
        assert parsed["name"] == "test"
        assert parsed["count"] == 5
        assert "2025-01-15" in parsed["timestamp"]

    def test_rag_result_to_json(self):
        """Test RagResult to JSON."""
        result = RagResult(
            id="test-1",
            text="Test result",
            score=0.95,
            source="TestSource",
        )
        json_str = to_json(result, pretty=False)

        parsed = json.loads(json_str)
        assert parsed["id"] == "test-1"
        assert parsed["text"] == "Test result"
        assert parsed["score"] == 0.95


class TestFromJson:
    """Test from_json function."""

    def test_parse_simple_json(self):
        """Test parsing simple JSON."""
        json_str = '{"name": "test", "count": 5}'
        data = from_json(json_str)

        assert isinstance(data, dict)
        assert data["name"] == "test"
        assert data["count"] == 5

    def test_parse_complex_json(self):
        """Test parsing complex JSON."""
        json_str = '{"users": [{"name": "Alice"}, {"name": "Bob"}], "count": 2}'
        data = from_json(json_str)

        assert isinstance(data["users"], list)
        assert len(data["users"]) == 2
        assert data["users"][0]["name"] == "Alice"

    def test_invalid_json(self):
        """Test parsing invalid JSON."""
        with pytest.raises(json.JSONDecodeError):
            from_json("not valid json")


class TestToDict:
    """Test to_dict function."""

    def test_dataclass_to_dict(self):
        """Test dataclass to dict conversion."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        obj = SampleDataClass(name="test", count=5, timestamp=dt)
        result = to_dict(obj)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert result["count"] == 5
        assert isinstance(result["timestamp"], str)

    def test_rag_result_to_dict(self):
        """Test RagResult to dict conversion."""
        result = RagResult(
            id="test-1",
            text="Test result",
            score=0.95,
        )
        data = to_dict(result)

        assert isinstance(data, dict)
        assert data["id"] == "test-1"
        assert data["text"] == "Test result"

    def test_dict_to_dict(self):
        """Test dict to dict conversion (with serialization)."""
        dt = datetime(2025, 1, 15, 10, 30, 45)
        input_dict = {"name": "test", "timestamp": dt}
        result = to_dict(input_dict)

        assert isinstance(result, dict)
        assert result["name"] == "test"
        assert isinstance(result["timestamp"], str)

    def test_non_convertible_object(self):
        """Test error on non-convertible object."""

        class NonConvertible:
            pass

        with pytest.raises(TypeError):
            to_dict(NonConvertible())


class TestFormatJsonOutput:
    """Test format_json_output function."""

    def test_include_nulls(self):
        """Test including null values."""
        data = {"name": "test", "value": None, "count": 5}
        json_str = format_json_output(data, pretty=False, include_nulls=True)

        parsed = json.loads(json_str)
        assert "value" in parsed
        assert parsed["value"] is None

    def test_exclude_nulls(self):
        """Test excluding null values."""
        data = {"name": "test", "value": None, "count": 5}
        json_str = format_json_output(data, pretty=False, include_nulls=False)

        parsed = json.loads(json_str)
        assert "value" not in parsed
        assert parsed["name"] == "test"
        assert parsed["count"] == 5

    def test_nested_nulls(self):
        """Test excluding nulls from nested structures."""
        data = {
            "name": "test",
            "metadata": {"key1": "value1", "key2": None},
            "items": [1, None, 3],
        }
        json_str = format_json_output(data, pretty=False, include_nulls=False)

        parsed = json.loads(json_str)
        assert "key2" not in parsed["metadata"]
        # Note: None items in lists are removed, list becomes [1, 3]
        assert len(parsed["items"]) == 2


class TestThreadSafety:
    """Test thread-safety of serialization functions."""

    def test_concurrent_to_json(self):
        """Test concurrent JSON serialization."""

        def serialize_task(index: int) -> str:
            data = {"id": index, "name": f"test-{index}", "count": index * 10}
            return to_json(data, pretty=False)

        # Run 50 concurrent serialization tasks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(serialize_task, i) for i in range(50)]
            results = [f.result() for f in futures]

        # Verify all serializations succeeded
        assert len(results) == 50
        for i, json_str in enumerate(results):
            parsed = json.loads(json_str)
            assert parsed["id"] == i
            assert parsed["name"] == f"test-{i}"

    def test_concurrent_to_serializable(self):
        """Test concurrent to_serializable calls."""

        def serialize_task(index: int) -> dict:
            dt = datetime(2025, 1, 15, 10, 30, 45)
            obj = SampleDataClass(
                name=f"test-{index}",
                count=index,
                timestamp=dt,
                metadata={"index": index},
            )
            return to_serializable(obj)

        # Run 50 concurrent conversion tasks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(serialize_task, i) for i in range(50)]
            results = [f.result() for f in futures]

        # Verify all conversions succeeded
        assert len(results) == 50
        for i, data in enumerate(results):
            assert data["name"] == f"test-{i}"
            assert data["count"] == i
            assert data["metadata"]["index"] == i

    def test_concurrent_rag_results(self):
        """Test concurrent serialization of RagResult objects."""

        def serialize_task(index: int) -> str:
            result = RagResult(
                id=f"test-{index}",
                text=f"Result {index}",
                score=0.9 + (index % 10) / 100,
                source=f"Source-{index}",
            )
            return to_json(result, pretty=False)

        # Run 50 concurrent tasks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(serialize_task, i) for i in range(50)]
            results = [f.result() for f in futures]

        # Verify all serializations succeeded
        assert len(results) == 50
        for i, json_str in enumerate(results):
            parsed = json.loads(json_str)
            assert parsed["id"] == f"test-{i}"
            assert parsed["text"] == f"Result {i}"

    def test_reentrancy(self):
        """Test that serialization functions are reentrant."""

        def nested_serialize(depth: int) -> dict:
            if depth == 0:
                return {"depth": 0, "value": "base"}

            # Recursively call serialization
            nested = nested_serialize(depth - 1)
            data = {"depth": depth, "nested": nested}
            # Serialize and deserialize to test reentrancy
            json_str = to_json(data, pretty=False)
            return from_json(json_str)

        # Test nested calls up to 10 levels deep
        result = nested_serialize(10)

        assert result["depth"] == 10
        current = result
        for i in range(10, 0, -1):
            assert current["depth"] == i
            if i > 1:
                current = current["nested"]
