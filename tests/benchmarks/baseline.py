"""Performance baseline measurements for RAGDiff before library refactoring.

This script captures:
1. Performance metrics (latency, throughput, memory)
2. Sample query outputs for correctness validation

NOTE: Current CLI has inconsistent output handling - some log output mixed with JSON.
This will be addressed in the library refactoring to ensure clean programmatic access.

Results are saved to:
- baseline_results.json (performance metrics)
- baseline_outputs.json (sample query outputs - best effort capture)
"""

import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil


@dataclass
class LatencyMetrics:
    """Latency measurements in milliseconds."""

    average: float
    p50: float
    p95: float
    p99: float
    min: float
    max: float


@dataclass
class PerformanceBaseline:
    """Complete performance baseline measurements."""

    single_query_latency_ms: LatencyMetrics
    batch_throughput_qps: float  # queries per second
    memory_rss_mb: float  # RSS memory in MB
    memory_peak_mb: float  # Peak memory in MB
    cli_startup_time_ms: float
    python_version: str
    timestamp: str


def measure_memory_mb() -> tuple[float, float]:
    """Measure current RSS and peak memory in MB."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024, mem_info.rss / 1024 / 1024


def measure_cli_startup_ms() -> float:
    """Measure CLI startup time."""
    start = time.time()
    subprocess.run(
        ["python3", "-c", "from ragdiff.cli import app; pass"],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        check=True,
    )
    end = time.time()
    return (end - start) * 1000


def measure_single_query_latency(
    query: str, config_path: str, runs: int = 10
) -> tuple[LatencyMetrics, dict[str, Any]]:
    """Measure single query latency over multiple runs.

    Returns:
        Tuple of (latency metrics, sample output from first successful run)
    """
    latencies = []
    sample_output = None

    for i in range(runs):
        start = time.time()
        result = subprocess.run(
            [
                "python3",
                "-m",
                "ragdiff.cli",
                "compare",
                query,
                "--config",
                config_path,
                "--top-k",
                "5",
                "--format",
                "json",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            check=False,
        )
        end = time.time()

        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)

        # Capture sample output from first run for correctness validation
        if i == 0:
            sample_output = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "note": "Raw output for manual inspection and future comparison",
            }

    latencies_sorted = sorted(latencies)
    return (
        LatencyMetrics(
            average=statistics.mean(latencies),
            p50=latencies_sorted[len(latencies_sorted) // 2],
            p95=latencies_sorted[int(len(latencies_sorted) * 0.95)],
            p99=latencies_sorted[int(len(latencies_sorted) * 0.99)],
            min=min(latencies),
            max=max(latencies),
        ),
        sample_output,
    )


def measure_batch_throughput(
    queries_file: str, config_path: str
) -> tuple[float, dict[str, Any]]:
    """Measure batch query throughput.

    Returns:
        Tuple of (queries per second, sample output)
    """
    start = time.time()
    result = subprocess.run(
        [
            "python3",
            "-m",
            "ragdiff.cli",
            "batch",
            queries_file,
            "--config",
            config_path,
            "--top-k",
            "5",
            "--format",
            "json",
        ],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=False,
    )
    end = time.time()

    elapsed = end - start

    # Count queries
    with open(queries_file) as f:
        query_count = len([line for line in f if line.strip()])

    qps = query_count / elapsed if elapsed > 0 else 0

    # Capture raw output
    sample_output = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "note": "Raw output for manual inspection and future comparison",
    }

    return qps, sample_output


def run_baseline() -> tuple[PerformanceBaseline, dict[str, Any]]:
    """Run complete baseline measurements.

    Returns:
        Tuple of (performance baseline, sample outputs)
    """
    print("Running RAGDiff Performance Baseline...")
    print("=" * 60)

    # Setup
    project_root = Path(__file__).parent.parent.parent
    config_path = str(project_root / "configs" / "tafsir.yaml")
    test_query = "What is the meaning of Surah Al-Fatiha?"

    # Create temporary queries file for batch test
    queries_file = project_root / "tmp" / "baseline_queries.txt"
    queries_file.parent.mkdir(exist_ok=True)
    queries_file.write_text(
        "\n".join(
            [
                "What is the meaning of Surah Al-Fatiha?",
                "Explain the concept of Tawhid",
                "What are the pillars of Islam?",
            ]
        )
    )

    # Measure CLI startup
    print("\n1. Measuring CLI startup time...")
    startup_ms = measure_cli_startup_ms()
    print(f"   ✓ Startup: {startup_ms:.2f}ms")

    # Measure single query latency
    print("\n2. Measuring single query latency (10 runs)...")
    latency_metrics, single_outputs = measure_single_query_latency(
        test_query, config_path, runs=10
    )
    print(f"   ✓ Average: {latency_metrics.average:.2f}ms")
    print(f"   ✓ P50: {latency_metrics.p50:.2f}ms")
    print(f"   ✓ P95: {latency_metrics.p95:.2f}ms")
    print(f"   ✓ P99: {latency_metrics.p99:.2f}ms")

    # Measure batch throughput
    print("\n3. Measuring batch throughput...")
    throughput_qps, batch_outputs = measure_batch_throughput(
        str(queries_file), config_path
    )
    print(f"   ✓ Throughput: {throughput_qps:.2f} queries/sec")

    # Measure memory
    print("\n4. Measuring memory usage...")
    rss_mb, peak_mb = measure_memory_mb()
    print(f"   ✓ RSS: {rss_mb:.2f}MB")
    print(f"   ✓ Peak: {peak_mb:.2f}MB")

    # Create baseline
    baseline = PerformanceBaseline(
        single_query_latency_ms=latency_metrics,
        batch_throughput_qps=throughput_qps,
        memory_rss_mb=rss_mb,
        memory_peak_mb=peak_mb,
        cli_startup_time_ms=startup_ms,
        python_version=sys.version,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    # Collect sample outputs for correctness validation
    sample_outputs = {
        "note": "Raw CLI outputs captured for correctness comparison after refactoring",
        "single_query": {
            "query": test_query,
            "sample_run": single_outputs,
        },
        "batch_query": {
            "queries_file": str(queries_file),
            "sample_run": batch_outputs,
        },
    }

    return baseline, sample_outputs


def main():
    """Run baseline and save results."""
    baseline, sample_outputs = run_baseline()

    # Save results
    output_dir = Path(__file__).parent
    results_file = output_dir / "baseline_results.json"
    outputs_file = output_dir / "baseline_outputs.json"

    # Convert dataclass to dict recursively
    def to_dict(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        return obj

    with open(results_file, "w") as f:
        json.dump(to_dict(baseline), f, indent=2)

    with open(outputs_file, "w") as f:
        json.dump(sample_outputs, f, indent=2)

    print("\n" + "=" * 60)
    print("✓ Baseline complete!")
    print(f"  Performance: {results_file}")
    print(f"  Outputs:     {outputs_file}")


if __name__ == "__main__":
    main()
