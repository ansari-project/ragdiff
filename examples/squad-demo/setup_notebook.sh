#!/bin/bash

# Setup script for SQuAD demo notebook
# Run this from the project root: examples/squad-demo/setup_notebook.sh

echo "Setting up SQuAD demo notebook environment..."

# Ensure we're in the examples/squad-demo directory
cd "$(dirname "$0")"

echo "Installing Python dependencies..."
uv pip install datasets faiss-cpu sentence-transformers numpy

echo ""
echo "✓ Setup complete!"
echo ""
echo "To start the notebook, run:"
echo "  cd examples/squad-demo"
echo "  uv run jupyter notebook"
