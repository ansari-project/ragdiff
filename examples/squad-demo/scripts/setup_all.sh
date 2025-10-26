#!/bin/bash
# Master setup script for SQuAD demo
# This script runs all setup steps in the correct order

set -e  # Exit on error

echo "=========================================="
echo "RAGDiff FAISS Example Setup"
echo "=========================================="
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Step 1/4: Downloading and preparing SQuAD dataset..."
echo "--------------------------------------------------"
python3 setup_dataset.py
echo ""

echo "Step 2/4: Building FAISS index with L2 distance..."
echo "--------------------------------------------------"
python3 build_faiss_l2.py
echo ""

echo "Step 3/4: Building FAISS index with Inner Product..."
echo "--------------------------------------------------"
python3 build_faiss_ip.py
echo ""

echo "Step 4/4: Generating query sets..."
echo "--------------------------------------------------"
python3 generate_queries.py
echo ""

echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "You can now run RAGDiff comparisons:"
echo ""
echo "  # Run queries against L2 index"
echo "  uv run ragdiff run squad-demo faiss-l2 referenced-queries --domains-dir examples"
echo ""
echo "  # Run queries against Inner Product index"
echo "  uv run ragdiff run squad-demo faiss-ip referenced-queries --domains-dir examples"
echo ""
echo "  # Compare the two runs"
echo "  uv run ragdiff compare squad-demo <run-id-1> <run-id-2> --domains-dir examples"
echo ""
