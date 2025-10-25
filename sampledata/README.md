# Sample Data Scripts for MongoDB RAG Testing

This directory contains scripts for setting up MongoDB Atlas with the SQuAD dataset for RAG testing with RAGDiff.

## Overview

These scripts help you:
1. **Load SQuAD dataset** into MongoDB Atlas with vector embeddings
2. **Sample test queries** for batch RAG evaluation

## Prerequisites

### 1. MongoDB Atlas Setup

- Create a MongoDB Atlas account at https://www.mongodb.com/cloud/atlas
- Create a cluster (M10+ tier required for vector search)
- Get your connection string from the Atlas UI
- Whitelist your IP address

### 2. OpenAI API Key

- Sign up at https://platform.openai.com/
- Create an API key
- Set billing limits to avoid unexpected charges

### 3. Install Dependencies

```bash
# Install MongoDB adapter dependencies
uv pip install -e ".[mongodb]"

# Or manually install
pip install pymongo openai tqdm
```

### 4. Set Environment Variables

```bash
# MongoDB Atlas connection string
export MONGODB_URI='mongodb+srv://username:password@cluster.mongodb.net/'

# OpenAI API key for embeddings
export OPENAI_API_KEY='sk-...'
```

## Script 1: Load SQuAD Dataset into MongoDB

The `load_squad_to_mongodb.py` script downloads the SQuAD v2.0 dataset, generates embeddings for each context passage, and loads them into MongoDB.

### Basic Usage

```bash
# Load full SQuAD dev set (default settings)
python sampledata/load_squad_to_mongodb.py

# Customize database and collection names
python sampledata/load_squad_to_mongodb.py \
  --database my_squad_db \
  --collection my_contexts

# Test with limited documents (faster, cheaper)
python sampledata/load_squad_to_mongodb.py --limit 100
```

### Command-Line Options

- `--database NAME` - MongoDB database name (default: squad_db)
- `--collection NAME` - MongoDB collection name (default: contexts)
- `--model MODEL` - OpenAI embedding model (default: text-embedding-3-small)
  - Options: text-embedding-3-small (1536 dims), text-embedding-3-large (3072 dims)
- `--squad-file PATH` - Path to SQuAD JSON file (downloads if not exists)
- `--skip-download` - Skip downloading dataset (use existing file)
- `--limit N` - Limit number of documents to process (for testing)

### What It Does

1. **Downloads SQuAD v2.0** development set (~6,000 context passages)
2. **Generates embeddings** using OpenAI API (takes ~10-15 minutes for full dataset)
3. **Inserts documents** into MongoDB with structure:
   ```json
   {
     "text": "The context passage...",
     "source": "Article_Title",
     "article_title": "Article_Title",
     "embedding": [0.123, -0.456, ...],  // 1536 or 3072 dimensions
     "questions": [
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
4. **Prints instructions** for creating the vector search index

### Cost Estimates

Using `text-embedding-3-small` model:
- Full SQuAD dev set (~6,000 contexts): ~$0.15-0.20
- Limited test (100 contexts): ~$0.003

### Creating the Vector Search Index

After loading data, create a vector search index in MongoDB Atlas:

**Method 1: Atlas UI**
1. Go to your cluster in Atlas
2. Navigate to: Database > [your_database] > [your_collection]
3. Click "Create Index" > "Atlas Vector Search"
4. Use the index definition printed by the script
5. Name it `vector_index`

**Method 2: Atlas CLI or API**
Use the JSON definition printed by the script.

**Index Definition Example:**
```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "dotProduct"
    },
    {
      "type": "filter",
      "path": "article_title"
    },
    {
      "type": "filter",
      "path": "num_questions"
    }
  ]
}
```

## Script 2: Sample Test Questions

The `sample_squad_questions.py` script extracts random questions from the SQuAD dataset for batch testing.

### Basic Usage

```bash
# Sample 100 questions (default)
python sampledata/sample_squad_questions.py

# Sample 50 answerable questions only
python sampledata/sample_squad_questions.py \
  --count 50 \
  --answerable-only

# Save with metadata as JSONL
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

### Output Formats

**Plain text (default):**
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

### 1. Load SQuAD Dataset

```bash
# Set environment variables
export MONGODB_URI='mongodb+srv://user:pass@cluster.mongodb.net/'
export OPENAI_API_KEY='sk-...'

# Load dataset (test with 100 documents first)
python sampledata/load_squad_to_mongodb.py --limit 100

# Create vector search index in Atlas UI (follow printed instructions)
```

### 2. Sample Test Questions

```bash
# Sample 100 questions for testing
python sampledata/sample_squad_questions.py \
  --count 100 \
  --output inputs/squad-100-questions.txt
```

### 3. Configure RAGDiff

Create `configs/squad-mongodb.yaml`:

```yaml
tools:
  mongodb:
    api_key_env: MONGODB_URI
    options:
      database: squad_db
      collection: contexts
      index_name: vector_index
      embedding_provider: openai
      embedding_model: text-embedding-3-small
      embedding_api_key_env: OPENAI_API_KEY
    timeout: 60
    default_top_k: 5

llm:
  model: claude-sonnet-4-5
  api_key_env: ANTHROPIC_API_KEY
```

### 4. Run RAGDiff Batch Evaluation

```bash
# Batch process all questions
uv run ragdiff batch inputs/squad-100-questions.txt \
  --config configs/squad-mongodb.yaml \
  --output-dir results/ \
  --top-k 5

# Evaluate results
uv run ragdiff compare results/ --output evaluation.jsonl

# Generate markdown report
uv run ragdiff compare results/ --format markdown --output report.md
```

### 5. Test Single Query

```bash
# Test a single question
uv run ragdiff query "What is the capital of France?" \
  --tool mongodb \
  --config configs/squad-mongodb.yaml \
  --top-k 5
```

## Troubleshooting

### "No module named 'pymongo'"
```bash
uv pip install -e ".[mongodb]"
```

### "Environment variable MONGODB_URI is not set"
```bash
export MONGODB_URI='mongodb+srv://user:pass@cluster.mongodb.net/'
```

### "OpenAI API key error"
```bash
export OPENAI_API_KEY='sk-...'
```

### "Vector search index not found"
- Make sure you created the vector search index in Atlas
- Index name must be `vector_index` (or update config)
- Wait a few minutes after creating index for it to build

### Slow embedding generation
- Use `--limit` to test with fewer documents first
- The full dataset takes ~10-15 minutes
- OpenAI has rate limits - the script includes delays

## Dataset Information

**SQuAD v2.0 (Stanford Question Answering Dataset)**
- **Dev set**: ~6,000 context passages, ~12,000 questions
- **Topics**: Wide range (Wikipedia articles)
- **Question types**: Answerable and unanswerable questions
- **License**: CC BY-SA 4.0
- **Source**: https://rajpurkar.github.io/SQuAD-explorer/

## Cost Estimates

### OpenAI Embeddings
- Model: text-embedding-3-small
- Cost: $0.00002 per 1K tokens
- Full SQuAD dev set: ~$0.15-0.20
- 100 documents: ~$0.003

### MongoDB Atlas
- Vector search requires M10+ cluster
- M10 tier: ~$57/month (or ~$0.08/hour)
- Free tier (M0) does not support vector search

### Total for Testing
- Initial setup: <$1
- Monthly if keeping cluster running: ~$60
- Recommendation: Use Atlas free trial or delete cluster when done

## Next Steps

After setting up:

1. **Experiment with different embedding models**
   - Compare text-embedding-3-small vs text-embedding-3-large
   - Test different similarity metrics (dotProduct, cosine, euclidean)

2. **Compare with other RAG systems**
   - Add Vectara, Agentset, or other tools to your config
   - Run side-by-side comparisons

3. **Optimize retrieval**
   - Tune `num_candidates` parameter
   - Try metadata filtering
   - Experiment with different `top_k` values

4. **Evaluate quality**
   - Use LLM evaluation to assess result quality
   - Compare against SQuAD ground truth answers
   - Measure answer accuracy

## References

- [MongoDB Atlas Vector Search](https://www.mongodb.com/docs/atlas/atlas-vector-search/)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [SQuAD Dataset](https://rajpurkar.github.io/SQuAD-explorer/)
- [RAGDiff Documentation](../README.md)
