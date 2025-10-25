# Specification: MongoDB Atlas Vector Search Adapter

**Status:** Completed
**Date:** 2025-10-25
**Author:** Claude (AI Assistant)

## Overview

Add MongoDB Atlas Vector Search as a new RAG backend adapter for RAGDiff, enabling users to perform semantic search using MongoDB's native vector search capabilities and compare results with other RAG systems.

## Motivation

MongoDB Atlas Vector Search provides several compelling advantages:

1. **Unified Platform**: Developers can use their existing MongoDB infrastructure for both operational data and vector search, eliminating the need for separate vector databases
2. **Mature Ecosystem**: MongoDB has extensive tooling, SDKs, and enterprise support
3. **Hybrid Search**: Ability to combine vector search with traditional MongoDB queries and filters
4. **Cost Efficiency**: For teams already using MongoDB, this reduces infrastructure complexity
5. **Widespread Adoption**: MongoDB Atlas is widely used, making this adapter valuable for many users

## Goals

### Primary Goals
1. Implement a production-ready MongoDB Atlas Vector Search adapter following RAGDiff's adapter pattern
2. Support automatic query embedding generation using popular embedding providers (starting with OpenAI)
3. Provide comprehensive documentation and example configurations
4. Include sample data loading scripts for easy testing and evaluation

### Secondary Goals
1. Create reproducible test workflows using publicly available datasets (SQuAD)
2. Ensure extensibility for future embedding providers (Cohere, HuggingFace, etc.)
3. Document cost implications and optimization strategies
4. Provide comparison benchmarks against existing adapters

## Non-Goals

1. **Not implementing custom embedding models**: Will rely on external embedding APIs (OpenAI, etc.) rather than implementing our own embedding generation
2. **Not supporting MongoDB Community Edition**: Vector search requires MongoDB Atlas (M10+ clusters)
3. **Not implementing automatic index creation**: Users must manually create vector search indexes in Atlas
4. **Not supporting multiple databases/collections per adapter instance**: Each adapter instance targets one collection

## Requirements

### Functional Requirements

**FR1: Vector Search Integration**
- Adapter must use MongoDB's `$vectorSearch` aggregation pipeline stage
- Support configurable similarity metrics (dotProduct, cosine, euclidean)
- Support configurable `numCandidates` parameter for search tuning
- Return normalized results in RAGDiff's `RagResult` format

**FR2: Embedding Generation**
- Automatically generate query embeddings at search time
- Support OpenAI embedding models (text-embedding-3-small, text-embedding-3-large)
- Allow configurable embedding model selection
- Handle embedding API errors gracefully

**FR3: Configuration**
- Support flexible field mappings (vector_field, text_field, source_field)
- Allow custom metadata field extraction
- Support environment variable substitution for credentials
- Provide clear validation errors for missing/invalid configuration

**FR4: Sample Data Pipeline**
- Provide script to load SQuAD v2.0 dataset into MongoDB
- Generate embeddings for all documents
- Create properly structured documents compatible with vector search
- Support testing with limited document counts

**FR5: Testing Support**
- Provide script to sample random questions from SQuAD
- Support reproducible sampling with seeds
- Output in formats compatible with RAGDiff batch processing
- Include ground truth answers for evaluation

### Non-Functional Requirements

**NFR1: Performance**
- Query latency should be comparable to other adapters (< 2 seconds typical)
- Batch embedding generation should include rate limiting
- Connection pooling should be handled by pymongo driver

**NFR2: Reliability**
- Graceful handling of connection failures
- Clear error messages for common issues
- Automatic cleanup of MongoDB connections

**NFR3: Security**
- No hardcoded credentials
- Support for MongoDB connection strings with authentication
- Secure handling of API keys for embedding providers

**NFR4: Maintainability**
- Follow RAGDiff's established adapter pattern
- Comprehensive test coverage (configuration validation, field mappings, etc.)
- Clear documentation with examples

**NFR5: Cost Transparency**
- Document embedding generation costs
- Document MongoDB Atlas tier requirements
- Provide cost estimates for sample data loading

## Architecture

### Component Structure

```
src/ragdiff/adapters/
└── mongodb.py              # MongoDB adapter implementation

configs/
└── mongodb-example.yaml    # Example configuration with comments

sampledata/
├── README.md               # Complete setup and usage guide
├── load_squad_to_mongodb.py    # Load SQuAD dataset with embeddings
└── sample_squad_questions.py   # Sample questions for testing

tests/
└── test_adapters.py        # MongoDB adapter tests
```

### Data Flow

1. **Query Time:**
   ```
   User Query → MongoDB Adapter → Embedding API (OpenAI)
   → Query Vector → MongoDB $vectorSearch → Raw Results
   → Normalized RagResults → User
   ```

2. **Data Loading:**
   ```
   SQuAD Dataset → Parse Contexts → Embedding API (OpenAI)
   → Document + Vector → MongoDB Insert → Vector Index
   ```

### MongoDB Document Schema

```python
{
    "_id": ObjectId,           # MongoDB document ID
    "text": str,               # Main content (for RAG retrieval)
    "embedding": List[float],  # Vector embedding (1536 or 3072 dims)
    "source": str,             # Source identifier
    "metadata": {              # Custom metadata fields
        "article_title": str,
        "num_questions": int,
        # ... other fields
    }
}
```

### Vector Search Index Structure

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
      "path": "source"
    }
  ]
}
```

## Configuration Interface

### YAML Configuration

```yaml
tools:
  mongodb:
    api_key_env: MONGODB_URI
    options:
      # Required
      database: squad_db
      collection: contexts
      index_name: vector_index

      # Optional - Field mappings
      vector_field: embedding        # Default: "embedding"
      text_field: text              # Default: "text"
      source_field: source          # Default: "source"

      # Optional - Search tuning
      num_candidates: 150           # Default: 150
      metadata_fields:              # Default: []
        - article_title
        - num_questions

      # Optional - Embedding configuration
      embedding_provider: openai    # Default: "openai"
      embedding_model: text-embedding-3-small  # Default
      embedding_api_key_env: OPENAI_API_KEY   # Default

    timeout: 60
    default_top_k: 5
```

### Environment Variables

```bash
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/
OPENAI_API_KEY=sk-...
```

## Test Strategy

### Unit Tests
1. **Configuration Validation**
   - Test missing required fields (database, collection, index_name)
   - Test missing environment variables
   - Test invalid options

2. **Field Mappings**
   - Test default field mappings
   - Test custom field mappings
   - Test metadata field extraction

3. **Adapter Registration**
   - Test adapter is auto-registered
   - Test adapter can be retrieved from registry
   - Test adapter inherits from RagAdapter

4. **Factory Integration**
   - Test adapter creation via factory
   - Test with valid configuration

### Integration Tests (Manual)
1. Load SQuAD dataset to real MongoDB Atlas instance
2. Create vector search index
3. Run sample queries and verify results
4. Compare with other adapters (Vectara, Agentset)
5. Batch process 100 questions and evaluate

## Sample Data: SQuAD v2.0

### Why SQuAD?

1. **Well-Known**: Industry standard question answering dataset
2. **Publicly Available**: Free to download and use
3. **Good Size**: ~6,000 contexts, ~12,000 questions (dev set)
4. **Quality**: Professionally annotated with ground truth answers
5. **Diverse**: Wide range of topics from Wikipedia

### Dataset Structure

- **Source**: https://rajpurkar.github.io/SQuAD-explorer/
- **License**: CC BY-SA 4.0
- **Size**:
  - Dev set: ~6,000 context passages
  - ~12,000 questions (answerable + unanswerable)
- **Content**: Wikipedia articles across various topics

### Loading Process

1. Download SQuAD v2.0 dev set JSON
2. Parse into context passages
3. Generate embeddings using OpenAI API
4. Insert into MongoDB with proper schema
5. Create vector search index in Atlas

### Cost Estimates

**OpenAI Embeddings (text-embedding-3-small):**
- Full dataset (~6,000 contexts): ~$0.15-0.20
- Test subset (100 contexts): ~$0.003

**MongoDB Atlas:**
- Requires M10+ cluster for vector search
- M10 tier: ~$57/month or ~$0.08/hour
- Recommendation: Use free trial or delete when done

## Success Criteria

### Implementation Complete When:
- ✅ MongoDB adapter implements RagAdapter interface
- ✅ All configuration options are supported
- ✅ Adapter is auto-registered with registry
- ✅ Comprehensive tests are written and passing
- ✅ Example configuration is provided
- ✅ Documentation is complete

### Sample Data Complete When:
- ✅ SQuAD loading script is functional
- ✅ Question sampling script is functional
- ✅ Scripts include progress bars and error handling
- ✅ Comprehensive README with examples is written
- ✅ Cost estimates are documented

### Integration Complete When:
- ✅ Adapter works with RAGDiff CLI (query, batch, compare)
- ✅ Results can be compared with other adapters
- ✅ LLM evaluation works with MongoDB results

## Future Enhancements

### Phase 2 (Not in Initial Implementation)
1. **Additional Embedding Providers**
   - Cohere embeddings
   - HuggingFace models
   - Local embedding models (sentence-transformers)

2. **Advanced Features**
   - Metadata filtering in queries
   - Hybrid search (vector + text)
   - Multi-collection support
   - Automatic index creation via API

3. **Optimizations**
   - Caching of query embeddings
   - Batch query support
   - Connection pooling optimization

4. **Additional Datasets**
   - MS MARCO
   - Natural Questions
   - HotpotQA
   - Domain-specific datasets (medical, legal, etc.)

## Dependencies

### Python Packages
- `pymongo>=4.0.0` - MongoDB Python driver
- `openai>=1.0.0` - OpenAI API client for embeddings
- `tqdm` (optional) - Progress bars for scripts

### External Services
- MongoDB Atlas cluster (M10+ tier)
- OpenAI API account (for embeddings)

### RAGDiff Integration
- Uses existing `RagAdapter` ABC
- Uses existing adapter registry system
- Uses existing `RagResult` model
- Uses existing configuration system

## Risks and Mitigations

### Risk 1: MongoDB Atlas Cost
**Impact:** High
**Likelihood:** High
**Mitigation:**
- Document costs clearly in README
- Provide `--limit` flag for testing with small datasets
- Suggest free trial or time-limited testing

### Risk 2: Embedding API Rate Limits
**Impact:** Medium
**Likelihood:** Medium
**Mitigation:**
- Include rate limiting delays in scripts
- Support batch processing with retries
- Document rate limits clearly

### Risk 3: Vector Index Creation Complexity
**Impact:** Medium
**Likelihood:** Low
**Mitigation:**
- Provide exact index definition JSON
- Include screenshots in documentation
- Provide Atlas CLI commands as alternative

### Risk 4: Embedding Dimension Mismatches
**Impact:** High
**Likelihood:** Low
**Mitigation:**
- Validate embedding dimensions match index
- Clear error messages
- Document dimension requirements for each model

## References

- [MongoDB Atlas Vector Search Documentation](https://www.mongodb.com/docs/atlas/atlas-vector-search/)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [SQuAD Dataset](https://rajpurkar.github.io/SQuAD-explorer/)
- [RAGDiff Adapter Pattern](../resources/arch.md)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
