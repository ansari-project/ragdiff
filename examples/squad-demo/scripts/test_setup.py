#!/usr/bin/env python3
"""Test that the FAISS demo setup is complete and working.

This script verifies:
1. All required data files exist
2. FAISS indices are loadable
3. Documents are readable
4. Query sets are valid
"""

import json
import sys
from pathlib import Path


def check_file(path: Path, description: str) -> bool:
    """Check if a file exists and is readable."""
    if not path.exists():
        print(f"✗ {description}: NOT FOUND")
        print(f"  Expected: {path}")
        return False

    print(f"✓ {description}: OK")
    return True


def main() -> None:
    """Run setup verification tests."""
    script_dir = Path(__file__).parent
    demo_dir = script_dir.parent
    data_dir = demo_dir / "data"
    query_sets_dir = demo_dir / "query-sets"

    print("="*60)
    print("RAGDiff SQuAD Demo - Setup Verification")
    print("="*60)
    print()

    all_ok = True

    # Check data files
    print("Checking data files...")
    all_ok &= check_file(data_dir / "documents.jsonl", "Documents file")
    all_ok &= check_file(data_dir / "squad_raw.json", "Raw SQuAD data")
    all_ok &= check_file(data_dir / "faiss_l2.index", "FAISS L2 index")
    all_ok &= check_file(data_dir / "faiss_ip.index", "FAISS IP index")
    all_ok &= check_file(
        data_dir / "referenced-queries-metadata.json",
        "Query metadata"
    )
    print()

    # Check query sets
    print("Checking query sets...")
    all_ok &= check_file(
        query_sets_dir / "referenced-queries.txt",
        "Referenced queries"
    )
    all_ok &= check_file(
        query_sets_dir / "reference-free-queries.txt",
        "Reference-free queries"
    )
    print()

    # Validate documents file
    print("Validating documents...")
    docs_file = data_dir / "documents.jsonl"
    if docs_file.exists():
        try:
            doc_count = 0
            with open(docs_file, encoding="utf-8") as f:
                for line in f:
                    doc = json.loads(line)
                    if "id" not in doc or "text" not in doc:
                        print(f"✗ Document {doc_count} missing required fields")
                        all_ok = False
                        break
                    doc_count += 1

            print(f"✓ Validated {doc_count} documents")
        except Exception as e:
            print(f"✗ Error validating documents: {e}")
            all_ok = False
    print()

    # Validate query sets
    print("Validating query sets...")
    for query_file in [
        query_sets_dir / "referenced-queries.txt",
        query_sets_dir / "reference-free-queries.txt"
    ]:
        if query_file.exists():
            try:
                with open(query_file, encoding="utf-8") as f:
                    queries = [line.strip() for line in f if line.strip()]
                print(f"✓ {query_file.name}: {len(queries)} queries")
            except Exception as e:
                print(f"✗ Error reading {query_file.name}: {e}")
                all_ok = False
    print()

    # Try loading FAISS indices
    print("Testing FAISS index loading...")
    try:
        import faiss

        for idx_file in [
            data_dir / "faiss_l2.index",
            data_dir / "faiss_ip.index"
        ]:
            if idx_file.exists():
                try:
                    index = faiss.read_index(str(idx_file))
                    print(
                        f"✓ {idx_file.name}: {index.ntotal} vectors, "
                        f"{index.d} dimensions"
                    )
                except Exception as e:
                    print(f"✗ Error loading {idx_file.name}: {e}")
                    all_ok = False
    except ImportError:
        print("⚠ faiss-cpu not installed, skipping index loading test")
        print("  Install with: uv pip install faiss-cpu")
    print()

    # Final result
    print("="*60)
    if all_ok:
        print("✓ Setup verification PASSED")
        print()
        print("You can now run RAGDiff commands:")
        print()
        print("  uv run ragdiff run squad-demo faiss-l2 referenced-queries \\")
        print("    --domains-dir examples")
        print()
        print("  uv run ragdiff run squad-demo faiss-ip referenced-queries \\")
        print("    --domains-dir examples")
        return 0
    else:
        print("✗ Setup verification FAILED")
        print()
        print("Please run the setup script:")
        print("  cd examples/squad-demo")
        print("  ./scripts/setup_all.sh")
        return 1


if __name__ == "__main__":
    sys.exit(main())
