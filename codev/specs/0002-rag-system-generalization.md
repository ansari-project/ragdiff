# Specification: RAG System Generalization

## Overview
Generalize RAGDiff to support comparison of any RAG systems beyond the currently hardcoded Vectara/Mawsuah and Goodmem, making it easy to plug in and compare other popular RAG frameworks and services.

## Problem Statement

### Current Limitations
RAGDiff currently only supports two RAG systems:
1. **Vectara/Mawsuah**: Commercial RAG platform with custom API
2. **Goodmem**: Another commercial service with its own API

This creates several problems:
- **Limited applicability**: Can't compare other RAG systems (LangChain, LlamaIndex, custom implementations)
- **Hard to extend**: Adding a new RAG system requires understanding internal codebase structure
- **Framework lock-in**: Users can't evaluate different RAG frameworks against each other
- **Not useful for RAG developers**: People building custom RAG systems can't use this tool to evaluate their work

### User Need
RAG developers and teams need to:
- Compare different RAG frameworks (LangChain vs LlamaIndex vs custom)
- Evaluate different retrieval strategies (vector search, hybrid, reranking)
- Test different embedding models within the same framework
- Compare commercial RAG services vs open-source implementations
- Make data-driven decisions about which RAG approach to use

### Success Vision
A user should be able to:
1. Configure any RAG system (commercial or custom) in YAML
2. Run batch comparisons across multiple RAG implementations
3. Get LLM-as-judge evaluation of which system returned better results
4. Make informed decisions about which RAG approach to adopt

## Clarifying Questions

Before proceeding with the specification, I need to understand your requirements:

### 1. RAG System Priority
Which RAG systems/frameworks should we prioritize supporting?
- **LangChain** (popular Python framework)?
- **LlamaIndex** (data framework for LLMs)?
- **Haystack** (NLP framework with RAG support)?
- **OpenAI Assistants API** (with retrieval)?
- **Custom HTTP endpoints** (user's own RAG services)?
- **Local/self-hosted systems**?

### 2. Interface Flexibility
Should we support:
- Only **HTTP/REST APIs**?
- **Python SDK integrations** (directly import and call frameworks like LangChain)?
- **Both**?

### 3. Configuration Complexity
How much configuration flexibility is needed?
- **Simple**: Just API endpoint + auth token
- **Medium**: Request/response format mapping
- **Complex**: Framework-specific parameters (embedding model, chunk size, reranking, etc.)

### 4. Response Format Standardization
How should we handle different RAG systems returning different response formats?
- **Assume standard structure**: All return {text, score, source}
- **Custom parsers**: Allow users to write response mappers
- **Schema definition**: Define common schema and require adapters to map to it

### 5. Backward Compatibility
- Must existing Vectara/Goodmem configs continue to work unchanged?
- Can we migrate them to a new format with a migration script?
- Or can we make breaking changes?

### 6. Evaluation Criteria
Should evaluation criteria:
- Be the **same for all RAG systems** (current approach)?
- Allow **custom criteria per RAG type**?
- Support **user-defined evaluation prompts**?

### 7. Local vs Remote Systems
Do you need to support:
- **Only remote APIs** (HTTP endpoints)?
- **Local Python frameworks** (imported as libraries)?
- **Docker containers** (RAG systems running in containers)?
- **All of the above**?

### 8. Real-World Example
Can you describe a specific comparison you'd want to run? For example:
- "I want to compare LangChain with OpenAI embeddings vs LlamaIndex with local embeddings"
- "I want to compare my custom RAG API vs Vectara"
- Something else?

Please answer these questions so I can create an accurate specification that matches your actual needs!

---

**Status**: Awaiting Clarification
**Next Step**: Answer clarifying questions, then proceed to full specification
