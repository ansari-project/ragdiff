# RAGDiff v2.0.0 - Domain-Based Architecture Restructure

**Status**: Draft
**Version**: 2.0.0
**Created**: 2025-10-25
**SPIDER Phase**: Specification

## Overview

Restructure RAGDiff from an adapter-based comparison tool to a domain-centric experimentation framework. This is a breaking v2.0.0 change that reimagines how users organize, execute, and compare RAG experiments.

## Motivation

Current v1.x limitations:
- Adapters are too low-level (just API wrappers)
- No clear organization for experiments
- Config scattered across files and env vars
- Results not first-class objects
- Hard to track experiment history
- Can't compare different configurations of same tool

v2.0.0 goals:
- Domain-first organization
- Systems = Tool + Config (enables A/B testing)
- First-class Runs (versioned, timestamped, replayable)
- Clean separation: API-first, files optional
- Structured experiment tracking

## Core Concepts

### 1. Domain
Top-level organizational unit representing a knowledge area.

**Properties**:
- `name`: Unique identifier (e.g., "tafsir", "legal")
- `description`: Human-readable description
- `variables`: Dict of configuration variables
- `secrets`: Dict of secret references (API keys, etc.)
- `metadata`: Optional metadata (tags, owner, created_at, etc.)

**Examples**:
- "Islamic Tafsir" domain
- "Legal Documents" domain
- "Medical Knowledge" domain

**Relationships**:
- Contains multiple Systems
- Contains multiple Query Sets
- Scopes Runs and Comparisons

### 2. System
A RAG implementation = Tool + Configuration.

**Properties**:
- `name`: Unique identifier within domain (e.g., "vectara-mmr", "mongodb-v1")
- `domain`: Parent domain reference
- `tool`: Underlying RAG tool (e.g., "vectara", "mongodb", "agentset")
- `config`: Tool-specific configuration dict
- `metadata`: Optional metadata (description, created_at, etc.)

**Examples in "tafsir" domain**:
- `vectara-mmr`: Vectara with MMR reranking
- `vectara-slingshot`: Vectara with Slingshot reranking
- `mongodb-embeddings-v1`: MongoDB with sentence-transformers
- `mongodb-embeddings-v2`: MongoDB with OpenAI embeddings
- `agentset-default`: Agentset with default settings

**Relationships**:
- Belongs to exactly one Domain
- Executes Query Sets to produce Runs
- Multiple systems can use the same underlying tool with different configs

### 3. Query Set
Collection of queries, with two types.

**Type 1: Query Only**
```
What is Islamic inheritance law?
How do we calculate zakat?
What are the pillars of Islam?
```

**Type 2: Query + Reference**
```jsonl
{"query": "What is Islamic inheritance law?", "reference": "Inheritance is distributed according to fixed shares..."}
{"query": "How do we calculate zakat?", "reference": "Zakat is 2.5% of wealth held for one lunar year..."}
```

**Properties**:
- `name`: Unique identifier within domain
- `domain`: Parent domain reference
- `type`: "query_only" | "query_reference"
- `queries`: List of queries (strings for query_only, dicts for query_reference)
- `metadata`: Optional metadata (description, created_at, source, etc.)

**Relationships**:
- Belongs to exactly one Domain
- Can be executed against multiple Systems
- Multiple query sets per domain allowed

### 4. Run
Execution result: Query Set × System = Run.

**Properties**:
- `id`: Unique identifier (UUID)
- `domain`: Parent domain reference
- `system`: System used
- `query_set`: Query Set used
- `results`: List of results (one per query)
- `config`: Execution config (top_k, timeout, etc.)
- `timestamp`: When executed
- `metadata`: Duration, success rate, version info, etc.

**Result Structure** (per query):
```python
{
    "query": str,
    "retrieved": [
        {
            "text": str,
            "score": float,
            "metadata": dict  # source, chunk_id, etc.
        },
        ...
    ],
    "reference": str | None,  # If query_reference type
    "duration_ms": float,
    "error": str | None
}
```

**Relationships**:
- Belongs to exactly one Domain
- References one System
- References one Query Set
- Can be compared with other Runs in same Domain

### 5. Comparison
Analysis comparing multiple Runs within a Domain.

**Properties**:
- `id`: Unique identifier (UUID)
- `domain`: Parent domain reference
- `runs`: List of Run IDs being compared
- `evaluations`: List of evaluation results
- `timestamp`: When evaluated
- `evaluator_config`: LLM evaluator settings
- `metadata`: Summary statistics, etc.

**Evaluation Structure** (per query):
```python
{
    "query": str,
    "reference": str | None,
    "run_results": {
        "system-1": [...],
        "system-2": [...],
    },
    "evaluation": {
        "winner": str | None,  # system name or "tie"
        "reasoning": str,
        "scores": {
            "system-1": float,
            "system-2": float
        }
    }
}
```

**Relationships**:
- Belongs to exactly one Domain
- References multiple Runs (all from same Domain)
- Produces evaluation output

**Constraints**:
- All Runs must be from the same Domain
- All Runs should use the same Query Set (or compatible ones)

## Data Models

### Python API Models (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime
from uuid import UUID, uuid4

class Domain(BaseModel):
    name: str
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # env var names
    metadata: dict[str, Any] = Field(default_factory=dict)

class System(BaseModel):
    name: str
    domain: str  # domain name
    tool: str  # "vectara", "mongodb", "agentset", etc.
    config: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

class QuerySet(BaseModel):
    name: str
    domain: str
    type: Literal["query_only", "query_reference"]
    queries: list[str] | list[dict[str, str]]  # depends on type
    metadata: dict[str, Any] = Field(default_factory=dict)

class RetrievedChunk(BaseModel):
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

class QueryResult(BaseModel):
    query: str
    retrieved: list[RetrievedChunk]
    reference: str | None = None
    duration_ms: float
    error: str | None = None

class Run(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    domain: str
    system: str  # system name
    query_set: str  # query set name
    results: list[QueryResult]
    config: dict[str, Any]  # top_k, timeout, etc.
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

class EvaluationResult(BaseModel):
    query: str
    reference: str | None
    run_results: dict[str, list[RetrievedChunk]]  # system -> chunks
    evaluation: dict[str, Any]  # winner, reasoning, scores

class Comparison(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    domain: str
    runs: list[UUID]  # run IDs
    evaluations: list[EvaluationResult]
    timestamp: datetime = Field(default_factory=datetime.now)
    evaluator_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## API Design (Library Interface)

### Domain Management

```python
# Create domain
domain = ragdiff.create_domain(
    name="tafsir",
    description="Islamic Tafsir comparison",
    variables={"timeout": 30},
    secrets={"anthropic_key": "ANTHROPIC_API_KEY"}
)

# Get domain
domain = ragdiff.get_domain("tafsir")

# List domains
domains = ragdiff.list_domains()

# Update domain
ragdiff.update_domain("tafsir", variables={"timeout": 60})

# Delete domain
ragdiff.delete_domain("tafsir")
```

### System Management

```python
# Create system
system = ragdiff.create_system(
    domain="tafsir",
    name="vectara-mmr",
    tool="vectara",
    config={
        "api_key_env": "VECTARA_API_KEY",
        "corpus_id_env": "VECTARA_CORPUS_ID",
        "reranking": "mmr",
        "diversity_bias": 0.3
    }
)

# Get system
system = ragdiff.get_system(domain="tafsir", name="vectara-mmr")

# List systems in domain
systems = ragdiff.list_systems(domain="tafsir")

# Update system
ragdiff.update_system(
    domain="tafsir",
    name="vectara-mmr",
    config={"diversity_bias": 0.5}
)

# Delete system
ragdiff.delete_system(domain="tafsir", name="vectara-mmr")
```

### Query Set Management

```python
# Create query-only set
query_set = ragdiff.create_query_set(
    domain="tafsir",
    name="basic-test",
    type="query_only",
    queries=[
        "What is Islamic inheritance law?",
        "How do we calculate zakat?"
    ]
)

# Create query+reference set
query_set = ragdiff.create_query_set(
    domain="tafsir",
    name="annotated-eval",
    type="query_reference",
    queries=[
        {
            "query": "What is Islamic inheritance law?",
            "reference": "Inheritance is distributed..."
        }
    ]
)

# Load from file
query_set = ragdiff.load_query_set(
    domain="tafsir",
    name="from-file",
    path="queries.txt",  # auto-detect type
)

# Get query set
query_set = ragdiff.get_query_set(domain="tafsir", name="basic-test")

# List query sets
query_sets = ragdiff.list_query_sets(domain="tafsir")

# Delete query set
ragdiff.delete_query_set(domain="tafsir", name="basic-test")
```

### Run Execution

```python
# Execute single query
result = ragdiff.query(
    domain="tafsir",
    system="vectara-mmr",
    query="What is Islamic inheritance law?",
    top_k=5
)

# Execute query set -> produces Run
run = ragdiff.execute_run(
    domain="tafsir",
    system="vectara-mmr",
    query_set="basic-test",
    config={"top_k": 5, "timeout": 30}
)

# Get run
run = ragdiff.get_run(run_id=uuid)

# List runs
runs = ragdiff.list_runs(
    domain="tafsir",
    system="vectara-mmr",  # optional filter
    query_set="basic-test",  # optional filter
)

# Delete run
ragdiff.delete_run(run_id=uuid)
```

### Comparison

```python
# Compare runs
comparison = ragdiff.compare_runs(
    domain="tafsir",
    run_ids=[run1_id, run2_id],
    evaluator_config={
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.0
    }
)

# Get comparison
comparison = ragdiff.get_comparison(comparison_id=uuid)

# List comparisons
comparisons = ragdiff.list_comparisons(domain="tafsir")

# Delete comparison
ragdiff.delete_comparison(comparison_id=uuid)
```

## CLI Design

### Domain Commands

```bash
# Create domain
ragdiff domain create tafsir --description "Islamic Tafsir comparison"

# List domains
ragdiff domain list

# Show domain details
ragdiff domain show tafsir

# Delete domain
ragdiff domain delete tafsir
```

### System Commands

```bash
# Create system from config file
ragdiff system create tafsir vectara-mmr --config systems/vectara-mmr.yaml

# Create system inline
ragdiff system create tafsir mongodb-v1 \
  --tool mongodb \
  --config '{"uri_env": "MONGODB_URI", "database": "tafsir"}'

# List systems
ragdiff system list tafsir

# Show system details
ragdiff system show tafsir vectara-mmr

# Delete system
ragdiff system delete tafsir vectara-mmr
```

### Query Set Commands

```bash
# Create from file (auto-detect type)
ragdiff query-set create tafsir basic-test --file queries.txt

# Create from JSONL (query+reference)
ragdiff query-set create tafsir annotated --file queries.jsonl

# List query sets
ragdiff query-set list tafsir

# Show query set
ragdiff query-set show tafsir basic-test

# Delete query set
ragdiff query-set delete tafsir basic-test
```

### Run Commands

```bash
# Execute single query
ragdiff run query tafsir vectara-mmr "What is Islamic inheritance law?" --top-k 5

# Execute query set (creates Run)
ragdiff run execute tafsir vectara-mmr basic-test --top-k 5 --save

# List runs
ragdiff run list tafsir

# Show run details
ragdiff run show <run-id>

# Delete run
ragdiff run delete <run-id>
```

### Comparison Commands

```bash
# Compare runs
ragdiff compare <run-id-1> <run-id-2> --output comparison.jsonl

# Compare with custom evaluator
ragdiff compare <run-id-1> <run-id-2> \
  --model claude-3-5-sonnet-20241022 \
  --temperature 0.0

# List comparisons
ragdiff compare list tafsir

# Show comparison
ragdiff compare show <comparison-id>

# Delete comparison
ragdiff compare delete <comparison-id>
```

## File-Based Configuration (Optional)

Users can organize domains in directories:

```
domains/
  tafsir/
    domain.yaml              # Domain definition
    systems/
      vectara-mmr.yaml       # System configs
      vectara-slingshot.yaml
      mongodb-v1.yaml
    query-sets/
      basic-test.txt         # Query sets
      annotated.jsonl
    runs/                    # Saved runs (auto-generated)
      2025-10-25-123456-vectara-mmr-basic-test.json
    comparisons/             # Saved comparisons (auto-generated)
      2025-10-25-234567-vectara-vs-mongodb.jsonl
```

### domain.yaml
```yaml
name: tafsir
description: Islamic Tafsir comparison
variables:
  timeout: 30
  max_retries: 3
secrets:
  anthropic_key: ANTHROPIC_API_KEY
metadata:
  owner: ansari-project
  created_at: 2025-10-25
```

### systems/vectara-mmr.yaml
```yaml
name: vectara-mmr
tool: vectara
config:
  api_key_env: VECTARA_API_KEY
  corpus_id_env: VECTARA_CORPUS_ID
  reranking: mmr
  diversity_bias: 0.3
metadata:
  description: Vectara with MMR reranking
```

### query-sets/basic-test.txt
```
What is Islamic inheritance law?
How do we calculate zakat?
What are the pillars of Islam?
```

### query-sets/annotated.jsonl
```jsonl
{"query": "What is Islamic inheritance law?", "reference": "Inheritance is distributed according to fixed shares..."}
{"query": "How do we calculate zakat?", "reference": "Zakat is 2.5% of wealth held for one lunar year..."}
```

## Storage Backend

v2.0.0 will support pluggable storage backends:

1. **In-Memory** (default, for testing)
2. **File-Based** (JSON/YAML files in directories)
3. **SQLite** (local database)
4. **PostgreSQL** (production database) - future

```python
# Configure storage backend
ragdiff.configure_storage(
    backend="file",
    base_path="./domains"
)

# Or
ragdiff.configure_storage(
    backend="sqlite",
    db_path="./ragdiff.db"
)
```

## Migration Path (v1.x → v2.0.0)

No automatic migration - v2.0.0 is a clean break.

**Manual migration steps**:
1. Create Domain for each config file
2. Create Systems for each adapter + config combination
3. Create Query Sets from input files
4. Re-run experiments to generate Runs
5. Use new comparison workflow

**Migration helper** (optional):
```bash
ragdiff migrate from-v1 configs/tafsir.yaml --domain tafsir
```

This would:
- Create Domain "tafsir"
- Create Systems from adapter configs
- Suggest query set creation

## Success Criteria

### Functional Requirements
- [ ] Create/read/update/delete Domains
- [ ] Create/read/update/delete Systems
- [ ] Create/read/update/delete Query Sets
- [ ] Execute Runs (single query + query set)
- [ ] Store and retrieve Runs
- [ ] Compare Runs with LLM evaluation
- [ ] All operations work via Python API
- [ ] All operations work via CLI
- [ ] File-based config optional but supported

### Non-Functional Requirements
- [ ] Type-safe (Pydantic models, type hints)
- [ ] Well-tested (>200 tests)
- [ ] Clear error messages
- [ ] Fast (parallel execution where possible)
- [ ] Documented (README, API docs, examples)

### User Experience
- [ ] Clear mental model (Domain → System → Run → Comparison)
- [ ] Easy experimentation (A/B test different configs)
- [ ] Reproducible (Runs are versioned, timestamped)
- [ ] Flexible (API-first, file-based optional)

## Open Questions

1. **Versioning**: Should Systems/Query Sets be versioned? Or rely on Run timestamp?
2. **Sharing**: Should Domains/Systems/Query Sets be shareable (export/import)?
3. **Templates**: Should we provide domain/system templates for common use cases?
4. **Visualization**: Should we add visualization of comparison results?
5. **Batch execution**: Should we support batch execution of multiple systems × query sets?

## Self-Review Notes

### Critical Gaps Identified

**1. Tool/Adapter Layer (CRITICAL)**
- Systems reference "tools" but no definition of what tools are
- **Missing**: Tool interface/ABC, tool registry, configuration schemas
- **Impact**: This is the bridge between v1.x adapters and v2.0 systems
- **Resolution**: Must define Tool interface that wraps existing adapters

**2. Run Lifecycle & State Management**
- No run states (pending → running → completed/failed)
- **Missing**: Cancellation, retry logic, progress reporting
- **Missing**: Partial failure handling (some queries fail, some succeed)
- **Resolution**: Add `status` field to Run model with enum

**3. Storage Backend Interface (CRITICAL)**
- Mentions pluggable backends but no interface definition
- **Missing**: How to migrate between backends, transactions, concurrency
- **Resolution**: Define StorageBackend ABC with CRUD operations

**4. Pagination & Filtering**
- `list_*` operations have no pagination
- **Problem**: Breaks with 1000+ runs/systems
- **Resolution**: Add pagination params (limit, offset) and filters

**5. Error Handling Strategy**
- No exception hierarchy defined
- **Missing**: What errors each API method can raise
- **Resolution**: Define custom exceptions in planning phase

**6. Data Model Issues**
- `datetime.now()` should be `default_factory=lambda: datetime.utcnow()`
- **Missing**: Timezone specification (use UTC everywhere)
- **Missing**: Immutability guarantees on Runs
- **Resolution**: Fix in planning phase

**7. Validation & Constraints**
- No field validators (e.g., domain name format)
- No relationship integrity (e.g., system.domain must exist)
- **Resolution**: Add Pydantic validators in planning

**8. Secrets Management**
- Secrets referenced but implementation not defined
- **Missing**: How secrets are stored, retrieved, secured
- **Resolution**: Define in planning phase (env vars? vault? encrypted?)

**9. Concurrency Model**
- No discussion of concurrent run execution
- **Missing**: Thread safety, parallel queries, race conditions
- **Resolution**: Define concurrency guarantees in planning

**10. Comparison Scope**
- How to compare >2 runs?
- **Missing**: Pairwise vs all-at-once strategies
- **Resolution**: Start with 2 runs, extend in future

### Strengths
- Clear problem statement and motivation
- Well-defined core concepts with examples
- Clean, intuitive API design
- Comprehensive Pydantic models
- API-first with optional file config

### Updated Open Questions

1. **Tool Interface**: How do we define the tool layer? Reuse v1.x adapters?
2. **Run Immutability**: Should runs be immutable once created?
3. **Versioning**: How do we version systems/query sets? Just rely on timestamps?
4. **Large Query Sets**: How to handle 10k+ queries efficiently?
5. **Storage Migration**: How to migrate between storage backends?
6. **Multi-tenancy**: Single user or multi-tenant with isolation?
7. **Comparison N-way**: Support comparing >2 runs?
8. **Query Metadata**: Should individual queries have metadata (difficulty, category)?

## Next Steps (SPIDER-SOLO)

1. **Specification** ✓ (this document - after self-review)
2. **Planning**: Create implementation plan (address critical gaps)
3. **Implementation**: Execute in phases
4. **Defense**: Write comprehensive tests
5. **Evaluation**: Code review
6. **Reflection**: Update architecture docs
