# Sample Data Scripts for MongoDB RAG Testing

This directory contains scripts for setting up local MongoDB with the SQuAD dataset for RAG testing with RAGDiff.

## Overview

These scripts help you:
1. **Load SQuAD dataset** into local MongoDB with vector embeddings
2. **Sample test queries** in query set format for batch RAG evaluation

## Prerequisites

### 1. Local MongoDB Setup

#### Install MongoDB Community Edition

**macOS (Homebrew):**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Ubuntu/Debian:**
```bash
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt-get update
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
```

**Verify Installation:**
```bash
mongosh --eval "db.version()"
```

Your local MongoDB will be available at: `mongodb://localhost:27017/`

### 2. Install Dependencies

```bash
# Install MongoDB adapter dependencies with sentence-transformers
uv pip install -e ".[mongodb]"

# Or manually install
pip install pymongo sentence-transformers tqdm
```

### 3. Set Environment Variables

```bash
# Local MongoDB connection string
export MONGODB_URI='mongodb://localhost:27017/'

# No API keys needed - sentence-transformers runs locally!
```

## Script 1: Load SQuAD Dataset into MongoDB

The `load_squad_to_mongodb.py` script downloads the SQuAD v2.0 dataset, generates embeddings using local sentence-transformers, and loads them into MongoDB.

### Basic Usage

```bash
# Load full SQuAD dev set (default settings)
python sampledata/load_squad_to_mongodb.py

# Customize database and collection names
python sampledata/load_squad_to_mongodb.py \
  --database my_squad_db \
  --collection my_contexts

# Test with limited documents (faster)
python sampledata/load_squad_to_mongodb.py --limit 100

# Use a different embedding model
python sampledata/load_squad_to_mongodb.py \
  --model all-mpnet-base-v2
```

### Command-Line Options

- `--database NAME` - MongoDB database name (default: squad_db)
- `--collection NAME` - MongoDB collection name (default: contexts)
- `--model MODEL` - Sentence-transformer model (default: all-MiniLM-L6-v2)
  - Options: all-MiniLM-L6-v2 (384 dims, fast), all-mpnet-base-v2 (768 dims, better quality)
- `--squad-file PATH` - Path to SQuAD JSON file (downloads if not exists)
- `--skip-download` - Skip downloading dataset (use existing file)
- `--limit N` - Limit number of documents to process (for testing)

### What It Does

1. **Downloads SQuAD v2.0** development set (~6,000 context passages)
2. **Generates embeddings** using sentence-transformers locally (takes ~5-10 minutes for full dataset)
3. **Inserts documents** into MongoDB with structure:
   ```json
   {
     "text": "The context passage...",
     "source": "Article_Title",
     "article_title": "Article_Title",
     "embedding": [0.123, -0.456, ...],  // 384 or 768 dimensions
     "questions": [              // Questions are METADATA, not being embedded
       {
         "id": "5a123...",
         "question": "What is...",
         "is_impossible": false,
         "answers": ["answer text"]
       }
     ],
     "num_questions": 3
   }
   ```

   **Note:** The `questions` field stores metadata about which questions map to this context passage. The questions themselves are NOT being embedded here - only the context passages are embedded for retrieval.

4. **Prints instructions** for creating the vector search index

### Cost Estimates

Using sentence-transformers:
- **Completely free!** No API costs
- Runs entirely on your local machine
- One-time download of model (~100MB)
- CPU/GPU usage during embedding generation

### Creating the Vector Search Index

After loading data, you can create a vector search index using `mongosh` or MongoDB Compass.

**Using mongosh:**
```javascript
use squad_db

db.contexts.createIndex(
  { "embedding": "2dsphere" },
  { name: "vector_index" }
)
```

**Note:** MongoDB Community Edition has basic vector support. For production vector search with $vectorSearch, you would need MongoDB Atlas. However, for local development and testing, you can use basic similarity search.

## Script 2: Sample Test Questions

The `sample_squad_questions.py` script extracts random questions from the SQuAD dataset for batch testing.

### Basic Usage

```bash
# Sample 100 questions (default) in query set format
python sampledata/sample_squad_questions.py

# Sample 50 answerable questions only
python sampledata/sample_squad_questions.py \
  --count 50 \
  --answerable-only

# Save with full metadata as JSONL
python sampledata/sample_squad_questions.py \
  --count 100 \
  --jsonl \
  --output squad-100-questions.jsonl

# Reproducible sampling with seed
python sampledata/sample_squad_questions.py \
  --seed 42 \
  --count 100
```

### Command-Line Options

- `--squad-file PATH` - Path to SQuAD JSON file (default: squad-dev-v2.0.json)
- `--output PATH` - Output file path (default: squad-100-questions.txt)
- `--count N` - Number of questions to sample (default: 100)
- `--answerable-only` - Only sample answerable questions
- `--seed N` - Random seed for reproducibility
- `--jsonl` - Save as JSONL with metadata instead of plain text
- `--queryset` - Output in RAGDiff query set format (default: True)

### Output Formats

**Query Set Format (default):**
```json
{
  "queries": [
    {
      "id": "5a123...",
      "query": "What is the capital of France?",
      "metadata": {
        "article_title": "France",
        "is_impossible": false,
        "answers": ["Paris"]
      }
    },
    {
      "id": "5a124...",
      "query": "How many people live in Tokyo?",
      "metadata": {
        "article_title": "Tokyo",
        "is_impossible": false,
        "answers": ["13.96 million"]
      }
    }
  ]
}
```

**Plain text (with --no-queryset):**
```
What is the capital of France?
How many people live in Tokyo?
When was the first computer built?
```

**JSONL (with --jsonl):**
```json
{"id": "5a123...", "question": "What is...", "article_title": "Title", "answers": ["answer"]}
{"id": "5a124...", "question": "How many...", "article_title": "Title", "answers": ["42"]}
```

## Complete Workflow Example

### 1. Start Local MongoDB

```bash
# macOS
brew services start mongodb-community

# Ubuntu
sudo systemctl start mongod

# Verify it's running
mongosh --eval "db.version()"
```

### 2. Load SQuAD Dataset

```bash
# Set environment variable
export MONGODB_URI='mongodb://localhost:27017/'

# Load dataset (test with 100 documents first)
python sampledata/load_squad_to_mongodb.py --limit 100

# Model will download on first run (~100MB)
# Embedding generation will take a few minutes
```

### 3. Create Vector Index

```bash
mongosh
```
```javascript
use squad_db
db.contexts.createIndex({ "embedding": "2dsphere" }, { name: "vector_index" })
```

### 4. Sample Test Questions

```bash
# Sample 100 questions in query set format
python sampledata/sample_squad_questions.py \
  --count 100 \
  --output inputs/squad-100-queries.json \
  --queryset
```

### 5. Configure RAGDiff

Create `configs/squad-mongodb.yaml`:

```yaml
tools:
  mongodb:
    api_key_env: MONGODB_URI
    options:
      database: squad_db
      collection: contexts
      index_name: vector_index
      embedding_service: sentence-transformers
      embedding_model: all-MiniLM-L6-v2
    timeout: 60
    default_top_k: 5

llm:
  model: claude-sonnet-4-5
  api_key_env: ANTHROPIC_API_KEY
```

### 6. Run RAGDiff Batch Evaluation

```bash
# Batch process all questions
uv run ragdiff batch inputs/squad-100-queries.json \
  --config configs/squad-mongodb.yaml \
  --output-dir results/ \
  --top-k 5

# Evaluate results
uv run ragdiff compare results/ --output evaluation.jsonl

# Generate markdown report
uv run ragdiff compare results/ --format markdown --output report.md
```

### 7. Test Single Query

```bash
# Test a single question
uv run ragdiff query "What is the capital of France?" \
  --tool mongodb \
  --config configs/squad-mongodb.yaml \
  --top-k 5
```

## Troubleshooting

### "No module named 'sentence_transformers'"
```bash
pip install sentence-transformers
```

### "Connection refused to localhost:27017"
MongoDB isn't running. Start it:
```bash
# macOS
brew services start mongodb-community

# Ubuntu
sudo systemctl start mongod
```

### "Environment variable MONGODB_URI is not set"
```bash
export MONGODB_URI='mongodb://localhost:27017/'
```

### Model download is slow
First-time download of the embedding model (~100MB) might be slow depending on your internet connection. The model is cached locally after the first download.

### Out of memory during embedding
If you run out of RAM:
- Use `--limit` to process fewer documents
- Use a smaller model like `all-MiniLM-L6-v2` (default)
- Process in smaller batches

## Dataset Information

**SQuAD v2.0 (Stanford Question Answering Dataset)**
- **Dev set**: ~6,000 context passages, ~12,000 questions
- **Topics**: Wide range (Wikipedia articles)
- **Question types**: Answerable and unanswerable questions
- **License**: CC BY-SA 4.0
- **Source**: https://rajpurkar.github.io/SQuAD-explorer/

## Cost & Performance

### Sentence-Transformers Models

| Model | Dimensions | Speed | Quality | Size |
|-------|-----------|-------|---------|------|
| all-MiniLM-L6-v2 | 384 | Fast | Good | ~80MB |
| all-mpnet-base-v2 | 768 | Medium | Better | ~420MB |
| all-MiniLM-L12-v2 | 384 | Medium | Good | ~120MB |

### Processing Time (Full Dataset ~6,000 docs)

- **all-MiniLM-L6-v2**: ~5-10 minutes (CPU), ~2-3 minutes (GPU)
- **all-mpnet-base-v2**: ~10-15 minutes (CPU), ~3-5 minutes (GPU)

### Total Cost for Testing

- **MongoDB**: Free (local installation)
- **Embeddings**: Free (sentence-transformers, local)
- **Storage**: Minimal (~100MB for model + dataset)

**Recommendation**: Use local MongoDB for development, testing is completely free!

## Next Steps

After setting up:

1. **Experiment with different embedding models**
   - Compare all-MiniLM-L6-v2 vs all-mpnet-base-v2
   - Test different similarity calculations

2. **Compare with other RAG systems**
   - Add Vectara, Agentset, FAISS, or other tools to your config
   - Run side-by-side comparisons

3. **Optimize retrieval**
   - Try different similarity search approaches
   - Experiment with different `top_k` values
   - Test metadata filtering

4. **Evaluate quality**
   - Use LLM evaluation to assess result quality
   - Compare against SQuAD ground truth answers
   - Measure answer accuracy

## References

- [MongoDB Community Edition](https://www.mongodb.com/try/download/community)
- [Sentence-Transformers Documentation](https://www.sbert.net/)
- [SQuAD Dataset](https://rajpurkar.github.io/SQuAD-explorer/)
- [RAGDiff Documentation](../README.md)
