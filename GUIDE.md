# RAGDiff Configuration Guide

This guide explains RAGDiff's directory structure and YAML configuration formats in detail.

## Table of Contents

1. [Directory Structure](#directory-structure)
2. [Domain Configuration](#domain-configuration)
3. [System Configuration](#system-configuration)
4. [Query Sets](#query-sets)
5. [Run Results](#run-results)
6. [Comparison Results](#comparison-results)
7. [Environment Variables](#environment-variables)
8. [Examples](#examples)

## Directory Structure

RAGDiff uses a domain-based directory structure that organizes all artifacts by problem domain:

```
ragdiff-project/
├── domains/                      # All domain workspaces
│   ├── tafsir/                   # Example domain: Islamic tafsir
│   │   ├── domain.yaml           # Domain configuration
│   │   ├── providers/            # RAG provider configurations
│   │   │   ├── vectara-default.yaml
│   │   │   ├── mongodb-atlas.yaml
│   │   │   └── bm25-local.yaml
│   │   ├── query-sets/           # Test query collections
│   │   │   ├── basic-questions.txt
│   │   │   ├── complex-queries.txt
│   │   │   └── edge-cases.jsonl
│   │   ├── runs/                 # Execution results (auto-created)
│   │   │   └── 2024-10-29/       # Date-organized
│   │   │       ├── <run-id-1>.json
│   │   │       └── <run-id-2>.json
│   │   └── comparisons/          # Comparison results (auto-created)
│   │       └── 2024-10-29/       # Date-organized
│   │           └── <comparison-id>.json
│   └── legal/                    # Another domain example
│       ├── domain.yaml
│       ├── providers/
│       └── query-sets/
├── .env                          # API keys and secrets
└── .env.example                  # Template for environment variables
```

### Directory Purposes

- **`domains/`**: Root directory for all domain workspaces
- **`<domain>/domain.yaml`**: Defines the domain and its LLM evaluator settings
- **`<domain>/providers/`**: Contains RAG provider configurations (one YAML file per provider)
- **`<domain>/query-sets/`**: Stores reusable test query collections
- **`<domain>/runs/`**: Auto-created directory storing execution results
- **`<domain>/comparisons/`**: Auto-created directory storing comparison results

## Domain Configuration

The `domain.yaml` file defines a domain and its evaluation settings.

### Basic Structure

```yaml
name: my-domain
description: Description of what this domain covers
evaluator:
  model: gpt-4                    # LLM model for evaluation
  temperature: 0.0                # Temperature for consistency
  prompt_template: |              # Evaluation prompt
    Your evaluation prompt here...
```

### Full Example

```yaml
name: medical-qa
description: Medical question-answering comparison domain
evaluator:
  model: anthropic/claude-3-opus   # Any LiteLLM-supported model
  temperature: 0.0                 # 0.0 for deterministic evaluation
  max_tokens: 1000                 # Optional: max response tokens
  prompt_template: |
    You are evaluating two RAG system responses for medical questions.

    Question: {query}

    Response A ({provider_a}):
    {response_a}

    Response B ({provider_b}):
    {response_b}

    Evaluation criteria:
    1. Medical accuracy (40 points)
    2. Completeness (30 points)
    3. Relevance (20 points)
    4. Safety/disclaimers (10 points)

    Score each response 0-100 and determine the winner.

    Respond with JSON:
    {{
      "score_{provider_a}": <0-100>,
      "score_{provider_b}": <0-100>,
      "winner": "<provider_a, provider_b, or tie>",
      "reasoning": "Explanation of your decision"
    }}
```

### Evaluator Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | LiteLLM model identifier (e.g., `gpt-4`, `claude-3-opus`) |
| `temperature` | float | No | Sampling temperature (0.0-1.0), default: 0.0 |
| `max_tokens` | int | No | Maximum response tokens |
| `prompt_template` | string | Yes | Jinja2 template for evaluation prompt |

### Available Template Variables

- `{query}`: The original query
- `{provider_a}`, `{provider_b}`: System names being compared
- `{response_a}`, `{response_b}`: The responses from each system

## System Configuration

Provider YAML files in `providers/` directory define RAG provider connections.

### Common Structure

```yaml
name: system-name
description: Optional description
tool: vectara|mongodb|bm25s|agentset|openapi
config:
  # Tool-specific configuration
```

### Vectara Configuration

```yaml
name: vectara-production
description: Production Vectara corpus with reranking
tool: vectara
config:
  api_key: ${VECTARA_API_KEY}      # Environment variable substitution
  customer_id: ${VECTARA_CUSTOMER_ID}
  corpus_id: ${VECTARA_CORPUS_ID}
  rerank: true                     # Optional: enable reranking
  rerank_k: 100                    # Optional: rerank top K results
  timeout: 30                      # Optional: request timeout in seconds
```

### MongoDB Atlas Configuration

```yaml
name: mongodb-vector-search
description: MongoDB Atlas with vector search
tool: mongodb
config:
  connection_string: ${MONGODB_URI}
  database: rag_database
  collection: documents
  vector_index: vector_index       # Name of Atlas search index
  embedding_field: embedding       # Field containing vectors
  text_field: content              # Field containing text
  embedding_model: text-embedding-ada-002  # OpenAI embedding model
  embedding_dimensions: 1536       # Vector dimensions
```

### BM25 Local Configuration

```yaml
name: bm25-baseline
description: Local BM25 search baseline
tool: bm25s
config:
  index_path: ./indices/bm25_index.pkl
  documents_path: ./data/documents.jsonl
  language: english                # Optional: stemming language
  k1: 1.2                          # BM25 k1 parameter
  b: 0.75                          # BM25 b parameter
```

### Agentset Configuration

```yaml
name: agentset-semantic
description: Agentset semantic search
tool: agentset
config:
  api_token: ${AGENTSET_API_TOKEN}
  namespace_id: ${AGENTSET_NAMESPACE_ID}
  timeout: 30
  max_results: 10
```

### OpenAPI Adapter Configuration

```yaml
name: custom-api
description: Custom RAG API via OpenAPI
tool: openapi
config:
  base_url: https://api.example.com/v1
  api_key: ${CUSTOM_API_KEY}
  search_endpoint: /search
  search_method: POST
  query_param: q
  response_mapping:
    results_path: "data.results"
    text_path: "text"
    score_path: "relevance_score"
    metadata_path: "metadata"
```

### Environment Variable Substitution

Use `${VARIABLE_NAME}` syntax to reference environment variables:
- Keeps sensitive data out of configs
- Enables easy environment switching
- Variables are resolved at runtime
- Original variable names are preserved in run snapshots

## Query Sets

Query sets are collections of test queries stored in `query-sets/` directory.

### Plain Text Format (.txt)

One query per line:

```text
What is the capital of France?
Explain quantum computing in simple terms
How does photosynthesis work?
```

### JSONL Format (.jsonl)

For queries with metadata or expected answers:

```jsonl
{"query": "What is DNA?", "category": "biology", "difficulty": "basic"}
{"query": "Explain CRISPR", "category": "biology", "difficulty": "advanced", "reference": "CRISPR is a gene editing technology..."}
{"query": "How do vaccines work?", "category": "medicine", "difficulty": "intermediate"}
```

### Query Set Best Practices

1. **Diverse Coverage**: Include various query types and complexities
2. **Real-World Examples**: Use actual user queries when possible
3. **Edge Cases**: Include challenging or ambiguous queries
4. **Consistent Naming**: Use descriptive names (e.g., `medical-basic.txt`, `legal-complex.jsonl`)
5. **Version Control**: Track query sets in git for reproducibility

## Run Results

Runs are automatically saved to `runs/<date>/<run-id>.json` with complete execution details.

### Run Structure

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "label": "vectara-production-20241029-143022",
  "domain": "medical-qa",
  "system": "vectara-production",
  "query_set": "basic-questions",
  "status": "completed",
  "created_at": "2024-10-29T14:30:22Z",
  "results": [
    {
      "query": "What is DNA?",
      "chunks": [
        {
          "text": "DNA is a molecule that carries genetic information...",
          "score": 0.95,
          "metadata": {"source": "biology_textbook.pdf", "page": 42}
        }
      ],
      "duration_ms": 234,
      "error": null
    }
  ],
  "metadata": {
    "total_queries": 100,
    "successful": 98,
    "failed": 2,
    "duration_seconds": 45.2
  },
  "system_snapshot": {
    "name": "vectara-production",
    "tool": "vectara",
    "config": {"api_key": "${VECTARA_API_KEY}", "corpus_id": "12345"}
  },
  "query_set_snapshot": ["What is DNA?", "How do vaccines work?", ...]
}
```

## Comparison Results

Comparisons are saved to `comparisons/<date>/<comparison-id>.json`.

### Comparison Structure

```json
{
  "id": "660f9400-f31c-51e5-b827-557766551111",
  "label": "comparison-20241029-001",
  "domain": "medical-qa",
  "runs": ["run-id-1", "run-id-2"],
  "evaluations": [
    {
      "query": "What is DNA?",
      "evaluation": {
        "score_vectara-production": 85,
        "score_mongodb-atlas": 72,
        "winner": "vectara-production",
        "reasoning": "Vectara provided more accurate and complete information..."
      }
    }
  ],
  "evaluator_config": {
    "model": "gpt-4",
    "temperature": 0.0
  },
  "metadata": {
    "total_evaluations": 100,
    "successful_evaluations": 100,
    "failed_evaluations": 0,
    "duration_seconds": 120.5
  }
}
```

## Environment Variables

RAGDiff uses environment variables for sensitive configuration. Create a `.env` file in your project root:

### Example .env File

```bash
# Vectara Configuration
VECTARA_API_KEY=vaa_xxxxxxxxxxxxx
VECTARA_CUSTOMER_ID=1234567890
VECTARA_CORPUS_ID=1

# MongoDB Atlas
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

# Agentset
AGENTSET_API_TOKEN=ast_xxxxxxxxxxxxx
AGENTSET_NAMESPACE_ID=ns_xxxxxxxxxxxxx

# OpenAI (for embeddings and evaluation)
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Anthropic (for evaluation)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Google (for evaluation with Gemini)
GOOGLE_API_KEY=xxxxxxxxxxxxx

# Custom API endpoints
CUSTOM_API_KEY=xxxxxxxxxxxxx
CUSTOM_API_URL=https://api.example.com
```

### Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use `.env.example`** as a template (without real values)
3. **Rotate keys regularly** especially for production
4. **Use separate keys** for development and production
5. **Limit key permissions** to only what's needed

## Examples

### Complete Domain Setup Example

Let's create a complete legal document search comparison:

1. **Create domain structure**:
```bash
mkdir -p domains/legal/{providers,query-sets}
```

2. **Create domain.yaml**:
```yaml
# domains/legal/domain.yaml
name: legal
description: Legal document search and retrieval comparison
evaluator:
  model: gpt-4
  temperature: 0.0
  prompt_template: |
    Evaluate these legal document search results.

    Query: {query}

    System A ({provider_a}):
    {response_a}

    System B ({provider_b}):
    {response_b}

    Criteria:
    1. Legal accuracy and relevance (40%)
    2. Citation quality (30%)
    3. Completeness (20%)
    4. Clarity (10%)

    Return JSON with scores and winner.
```

3. **Create system configs**:
```yaml
# domains/legal/providers/pinecone-semantic.yaml
name: pinecone-semantic
tool: openapi
config:
  base_url: ${PINECONE_API_URL}
  api_key: ${PINECONE_API_KEY}
  # ... additional config
```

```yaml
# domains/legal/providers/elasticsearch-hybrid.yaml
name: elasticsearch-hybrid
tool: openapi
config:
  base_url: ${ELASTICSEARCH_URL}
  api_key: ${ELASTICSEARCH_API_KEY}
  # ... additional config
```

4. **Create query set**:
```text
# domains/legal/query-sets/contract-law.txt
What constitutes a breach of contract?
Explain the statute of limitations for personal injury claims
Define force majeure and its applications
What are the requirements for a valid will?
```

5. **Run comparisons**:
```bash
# Execute queries
ragdiff run legal pinecone-semantic contract-law
ragdiff run legal elasticsearch-hybrid contract-law

# Compare results
ragdiff compare legal <run-id-1> <run-id-2> --format markdown --output legal-comparison.md
```

## Tips and Best Practices

### Domain Design

1. **One domain per problem space**: Keep domains focused (e.g., "legal-contracts" not just "legal")
2. **Consistent evaluation criteria**: Use the same prompt template across a domain
3. **Version your domains**: Track changes in git
4. **Document assumptions**: Add comments in YAML files

### System Configuration

1. **Start simple**: Begin with minimal config, add complexity as needed
2. **Use descriptive names**: `vectara-with-rerank` instead of `vectara-v2`
3. **Document variations**: Explain what makes each system unique
4. **Test incrementally**: Verify each system works before comparing

### Query Sets

1. **Start small**: Begin with 10-20 queries for quick iteration
2. **Add progressively**: Expand to 100+ queries for thorough evaluation
3. **Include failure cases**: Test how providers handle impossible queries
4. **Track sources**: Note where queries came from (user logs, synthetic, etc.)

### Running Comparisons

1. **Use appropriate concurrency**: Start with 5-10, increase if stable
2. **Monitor rate limits**: Watch for 429 errors from APIs
3. **Save everything**: Runs are immutable snapshots for reproducibility
4. **Compare multiple times**: LLM evaluation can vary, even at temperature 0

## Troubleshooting

### Common Issues

**"Domain not found"**
- Check that `domains/<domain>/domain.yaml` exists
- Verify the domain name matches the directory name

**"System configuration not found"**
- Ensure provider YAML exists in `domains/<domain>/providers/`
- Check for typos in the system name

**"Environment variable not set"**
- Verify variable is defined in `.env`
- Check that `.env` is in the project root
- Ensure no spaces around `=` in `.env` file

**"API rate limit exceeded"**
- Reduce `--concurrency` parameter
- Add delays between requests
- Use different API keys for parallel runs

**"Evaluation failed"**
- Check LLM API key is valid
- Verify prompt template syntax
- Ensure model name is correct for LiteLLM

## Advanced Features

### Custom Providers

Implement the provider interface to add new RAG providers:

```python
from ragdiff.providers.base import Provider
from ragdiff.core.models import RetrievedChunk

class CustomProvider(Provider):
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        # Your implementation here
        results = self.custom_api_call(query)
        return [
            RetrievedChunk(
                text=r["content"],
                score=r["score"],
                metadata=r.get("metadata", {})
            )
            for r in results
        ]
```

### Batch Processing

Process multiple query sets efficiently:

```bash
# Create a batch script
for query_set in domains/legal/query-sets/*.txt; do
    basename=$(basename "$query_set" .txt)
    ragdiff run legal vectara-default "$basename" &
    ragdiff run legal mongodb-atlas "$basename" &
    wait
done
```

### Programmatic API

Use RAGDiff as a Python library:

```python
from ragdiff import execute_run, compare_runs

# Execute runs programmatically
run1 = execute_run(
    domain="legal",
    system="vectara-default",
    query_set="basic-questions",
    concurrency=10
)

run2 = execute_run(
    domain="legal",
    system="mongodb-atlas",
    query_set="basic-questions",
    concurrency=10
)

# Compare results
comparison = compare_runs(
    domain="legal",
    run_ids=[run1.id, run2.id],
    model="gpt-4"
)

# Access results
for evaluation in comparison.evaluations:
    print(f"Query: {evaluation.query}")
    print(f"Winner: {evaluation.evaluation['winner']}")
```

## Next Steps

1. **Explore the examples**: Check `examples/` directory for working demos
2. **Read the API docs**: See docstrings in `src/ragdiff/`
3. **Join discussions**: Open issues on GitHub for questions
4. **Contribute**: Submit PRs with new providers or features

For more information, see the main [README](README.md) or check the [llms-full.txt](llms-full.txt) for comprehensive technical details.
