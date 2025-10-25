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
- File-system-first: All config in YAML, runs stored as JSON
- Structured experiment tracking
- Simple CLI: Only run and compare commands

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
A RAG implementation = Tool + Configuration. Systems are defined in YAML files within a domain's directory.

**System Interface** (Code):
```python
class System(ABC):
    """A system accepts a query and returns a list of retrieved text chunks."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[str]:
        """
        Execute search and return list of text chunks.

        Args:
            query: The search query
            top_k: Number of results to return

        Returns:
            List of text chunks (strings), ordered by relevance
        """
        pass
```

**System Configuration** (YAML file):
```yaml
# domains/tafsir/systems/vectara-mmr.yaml
name: vectara-mmr
tool: vectara  # Which tool class to instantiate
config:
  api_key_env: VECTARA_API_KEY
  corpus_id_env: VECTARA_CORPUS_ID
  reranking: mmr
  diversity_bias: 0.3
metadata:
  description: Vectara with MMR reranking
```

**Examples in "tafsir" domain**:
- `vectara-mmr`: Vectara with MMR reranking
- `vectara-slingshot`: Vectara with Slingshot reranking
- `mongodb-embeddings-v1`: MongoDB with sentence-transformers
- `mongodb-embeddings-v2`: MongoDB with OpenAI embeddings

**Relationships**:
- Belongs to exactly one Domain (by directory location)
- Executes Query Sets to produce Runs
- Multiple systems can use the same underlying tool with different configs
- Defined in `domains/<domain>/systems/<system-name>.yaml`

### 3. Query Set
Collection of queries, with two types. **Maximum 1000 queries per query set.**

**Type 1: Query Only** (plain text file)
```
What is Islamic inheritance law?
How do we calculate zakat?
What are the pillars of Islam?
```

**Type 2: Query + Reference** (JSONL file)
```jsonl
{"query": "What is Islamic inheritance law?", "reference": "Inheritance is distributed according to fixed shares..."}
{"query": "How do we calculate zakat?", "reference": "Zakat is 2.5% of wealth held for one lunar year..."}
```

**File Locations**:
- Query-only: `domains/<domain>/query-sets/<name>.txt`
- Query+reference: `domains/<domain>/query-sets/<name>.jsonl`

**Constraints**:
- Maximum 1000 queries per query set
- Query set type auto-detected from file extension (.txt vs .jsonl)
- Each query must be non-empty after stripping whitespace

**Relationships**:
- Belongs to exactly one Domain (by directory location)
- Can be executed against multiple Systems
- Multiple query sets per domain allowed

### 4. Run
Execution result: Query Set × System = Run. Stored as JSON file in `domains/<domain>/runs/`.

**Run States**:
- `pending`: Run created but not started
- `running`: Currently executing queries
- `completed`: All queries executed successfully
- `failed`: Run failed (system error, timeout, etc.)
- `partial`: Some queries succeeded, some failed

**Properties**:
- `id`: Unique identifier (UUID)
- `domain`: Domain name
- `system`: System name
- `query_set`: Query Set name
- `status`: Run state (see above)
- `results`: List of results (one per query)
- `config`: Execution config (top_k, timeout, etc.)
- `started_at`: When execution started (ISO 8601 UTC)
- `completed_at`: When execution finished (ISO 8601 UTC)
- `metadata`: Duration, success rate, error count, version info

**Result Structure** (per query):
```python
{
    "query": str,
    "retrieved": list[str],  # List of text chunks (simplified!)
    "reference": str | None,  # If query_reference type
    "duration_ms": float,
    "error": str | None  # Error message if this query failed
}
```

**File Storage**:
```
domains/<domain>/runs/<run-id>.json
```

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "tafsir",
  "system": "vectara-mmr",
  "query_set": "basic-test",
  "status": "completed",
  "config": {"top_k": 5, "timeout": 30},
  "started_at": "2025-10-25T10:30:00Z",
  "completed_at": "2025-10-25T10:32:15Z",
  "results": [
    {
      "query": "What is Islamic inheritance law?",
      "retrieved": ["Chunk 1 text...", "Chunk 2 text..."],
      "reference": null,
      "duration_ms": 1250.5,
      "error": null
    }
  ],
  "metadata": {
    "total_queries": 10,
    "successful": 10,
    "failed": 0,
    "total_duration_ms": 12500
  }
}
```

**Relationships**:
- Belongs to exactly one Domain (by directory location)
- References one System (by name)
- References one Query Set (by name)
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

**Note**: These models are primarily for internal use and JSON serialization. Configuration is file-based (YAML), and runs are stored as JSON files.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

class RunStatus(str, Enum):
    """Run execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some queries succeeded, some failed

class Domain(BaseModel):
    """Domain configuration (loaded from domains/<domain>/domain.yaml)."""
    name: str
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # env var names
    metadata: dict[str, Any] = Field(default_factory=dict)

class SystemConfig(BaseModel):
    """System configuration (loaded from domains/<domain>/systems/<name>.yaml)."""
    name: str
    tool: str  # "vectara", "mongodb", "agentset", etc.
    config: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

class QuerySet(BaseModel):
    """Query set (loaded from domains/<domain>/query-sets/<name>.{txt,jsonl})."""
    name: str
    domain: str
    type: Literal["query_only", "query_reference"]
    queries: list[str] | list[dict[str, str]]  # depends on type

    @field_validator('queries')
    @classmethod
    def validate_max_queries(cls, v):
        if len(v) > 1000:
            raise ValueError("Query set cannot exceed 1000 queries")
        return v

class QueryResult(BaseModel):
    """Result for a single query within a run."""
    query: str
    retrieved: list[str]  # Simplified: just text chunks
    reference: str | None = None
    duration_ms: float
    error: str | None = None

class Run(BaseModel):
    """Run execution result (stored as domains/<domain>/runs/<id>.json)."""
    id: UUID = Field(default_factory=uuid4)
    domain: str
    system: str  # system name
    query_set: str  # query set name
    status: RunStatus
    results: list[QueryResult]
    config: dict[str, Any]  # top_k, timeout, etc.
    started_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator('started_at', 'completed_at')
    @classmethod
    def validate_utc(cls, v):
        """Ensure all timestamps are UTC."""
        if v and v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v

class EvaluationResult(BaseModel):
    """Evaluation result for comparing multiple runs on a single query."""
    query: str
    reference: str | None
    run_results: dict[str, list[str]]  # system name -> retrieved chunks
    evaluation: dict[str, Any]  # winner, reasoning, scores

class Comparison(BaseModel):
    """Comparison of multiple runs (stored as domains/<domain>/comparisons/<id>.json)."""
    id: UUID = Field(default_factory=uuid4)
    domain: str
    runs: list[UUID]  # run IDs being compared
    evaluations: list[EvaluationResult]
    created_at: datetime
    evaluator_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## File System Organization

All configuration and data is stored in the file system under a `domains/` directory:

```
domains/
  <domain-name>/
    domain.yaml              # Domain configuration
    systems/
      <system-name>.yaml     # System configurations (one per system)
    query-sets/
      <query-set-name>.txt   # Query-only sets
      <query-set-name>.jsonl # Query+reference sets
    runs/
      <run-id>.json          # Run results (auto-generated)
    comparisons/
      <comparison-id>.json   # Comparison results (auto-generated)
```

**Configuration Management**:
- Domains, systems, and query sets are managed by editing YAML/text files
- No CLI commands for CRUD operations on these entities
- CLI only supports executing runs and comparisons

**Example Setup**:
```bash
# Create domain structure manually
mkdir -p domains/tafsir/{systems,query-sets,runs,comparisons}

# Create domain.yaml
cat > domains/tafsir/domain.yaml <<EOF
name: tafsir
description: Islamic Tafsir comparison
variables:
  timeout: 30
secrets:
  anthropic_key: ANTHROPIC_API_KEY
EOF

# Create system config
cat > domains/tafsir/systems/vectara-mmr.yaml <<EOF
name: vectara-mmr
tool: vectara
config:
  api_key_env: VECTARA_API_KEY
  corpus_id_env: VECTARA_CORPUS_ID
  reranking: mmr
  diversity_bias: 0.3
EOF

# Create query set
cat > domains/tafsir/query-sets/basic-test.txt <<EOF
What is Islamic inheritance law?
How do we calculate zakat?
EOF

# Now use CLI to run and compare
ragdiff run tafsir vectara-mmr basic-test --top-k 5
```

## Library API (Internal)

The Python library provides internal functions for loading configuration and executing runs. These are primarily for CLI use, not end-user API.

### Configuration Loading

```python
# Internal functions for loading file-based config
from ragdiff.loader import load_domain, load_system, load_query_set

# Load domain config
domain = load_domain("tafsir")  # Reads domains/tafsir/domain.yaml

# Load system config
system = load_system("tafsir", "vectara-mmr")  # Reads domains/tafsir/systems/vectara-mmr.yaml

# Load query set
query_set = load_query_set("tafsir", "basic-test")  # Reads domains/tafsir/query-sets/basic-test.txt
```

### Run Execution

```python
# Execute a run (used by CLI)
from ragdiff.runner import execute_run

run = execute_run(
    domain="tafsir",
    system="vectara-mmr",
    query_set="basic-test",
    top_k=5,
    timeout=30
)
# Returns Run object and saves to domains/tafsir/runs/<run-id>.json
```

### Comparison

```python
# Compare runs (used by CLI)
from ragdiff.comparator import compare_runs

comparison = compare_runs(
    domain="tafsir",
    run_ids=["550e8400-...", "660f9511-..."],
    evaluator_model="claude-3-5-sonnet-20241022"
)
# Returns Comparison object and saves to domains/tafsir/comparisons/<comparison-id>.json
```

## CLI Design

The CLI only supports two operations: **running experiments** and **comparing results**. All configuration (domains, systems, query sets) is managed by editing YAML/text files directly.

### Run Command

Execute a query set against a system and save the results.

```bash
# Basic usage
ragdiff run <domain> <system> <query-set> [OPTIONS]

# Execute query set
ragdiff run tafsir vectara-mmr basic-test --top-k 5

# With timeout
ragdiff run tafsir vectara-mmr basic-test --top-k 5 --timeout 60

# Show progress
ragdiff run tafsir vectara-mmr basic-test --verbose

# Options:
#   --top-k INT         Number of results per query (default: 5)
#   --timeout INT       Timeout in seconds per query (default: 30)
#   --verbose          Show progress during execution
#   --output PATH      Custom output path (default: auto-generated in domains/<domain>/runs/)
```

**Output**:
- Creates run JSON file in `domains/<domain>/runs/<run-id>.json`
- Prints run ID to stdout for use in comparisons
- Shows summary statistics (total queries, success rate, duration)

**Example**:
```bash
$ ragdiff run tafsir vectara-mmr basic-test --top-k 5
Executing run...
├─ Loading domain: tafsir
├─ Loading system: vectara-mmr
├─ Loading query set: basic-test (10 queries)
├─ Running queries: [██████████] 10/10 (100%)
└─ Complete!

Run ID: 550e8400-e29b-41d4-a716-446655440000
Saved to: domains/tafsir/runs/550e8400-e29b-41d4-a716-446655440000.json

Summary:
- Total queries: 10
- Successful: 10
- Failed: 0
- Duration: 12.5s
```

### Compare Command

Compare two or more runs using LLM evaluation.

```bash
# Basic usage
ragdiff compare <run-id-1> <run-id-2> [OPTIONS]

# Compare two runs
ragdiff compare 550e8400-... 660f9511-...

# With custom evaluator
ragdiff compare 550e8400-... 660f9511-... \
  --model claude-3-5-sonnet-20241022 \
  --temperature 0.0

# With output format
ragdiff compare 550e8400-... 660f9511-... --format markdown

# Options:
#   --model TEXT        LLM model for evaluation (default: claude-3-5-sonnet-20241022)
#   --temperature FLOAT Temperature for LLM (default: 0.0)
#   --format TEXT       Output format: json, markdown, table (default: json)
#   --output PATH       Custom output path (default: auto-generated)
#   --verbose          Show progress during evaluation
```

**Output**:
- Creates comparison JSON file in `domains/<domain>/comparisons/<comparison-id>.json`
- Prints comparison results to stdout (format depends on --format)
- Shows summary statistics (win/loss/tie counts)

**Example**:
```bash
$ ragdiff compare 550e8400-... 660f9511-... --format markdown
Comparing runs...
├─ Loading runs from domain: tafsir
├─ Run 1: vectara-mmr (10 results)
├─ Run 2: mongodb-v1 (10 results)
├─ Evaluating with Claude...
├─ Queries: [██████████] 10/10 (100%)
└─ Complete!

Comparison ID: 770a8400-e29b-41d4-a716-446655440000

## Summary

| System       | Wins | Ties | Losses |
|--------------|------|------|--------|
| vectara-mmr  | 6    | 2    | 2      |
| mongodb-v1   | 2    | 2    | 6      |

**Winner**: vectara-mmr (60% win rate)

## Details

### Query 1: "What is Islamic inheritance law?"
**Winner**: vectara-mmr
**Reasoning**: Vectara returned more comprehensive and accurate results...

[... details for all queries ...]

Full results saved to: domains/tafsir/comparisons/770a8400-....json
```

### Utility Commands (Optional)

Helper commands for inspecting configuration and results:

```bash
# List available domains
ragdiff list-domains

# List systems in a domain
ragdiff list-systems tafsir

# List query sets in a domain
ragdiff list-query-sets tafsir

# List runs in a domain
ragdiff list-runs tafsir

# Show run details
ragdiff show-run <run-id>

# Show comparison details
ragdiff show-comparison <comparison-id>
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

### Resolved Based on User Feedback

**✅ 1. Tool/Adapter Layer** (RESOLVED)
- **Solution**: Systems ARE tools. Simple interface: `search(query: str, top_k: int) -> list[str]`
- **Decision**: Tools/adapters from v1.x become systems in v2.0
- **Impact**: Dramatically simplifies architecture

**✅ 2. Run Lifecycle & State Management** (RESOLVED)
- **Solution**: Added RunStatus enum (pending, running, completed, failed, partial)
- **Decision**: Includes partial state for when some queries fail
- **Impact**: Clear state tracking, progress reporting possible

**✅ 3. Storage Backend** (RESOLVED)
- **Solution**: No abstraction needed - file system only
- **Decision**: All config in YAML, all results in JSON files
- **Impact**: Simplified implementation, no database needed

**✅ 4. CLI Scope** (RESOLVED)
- **Solution**: CLI only supports `run` and `compare` commands
- **Decision**: No CRUD for domains/systems/query-sets (edit files directly)
- **Impact**: Simpler CLI, file-first approach

**✅ 5. Query Set Size Limit** (RESOLVED)
- **Solution**: Max 1000 queries per query set
- **Decision**: Enforced in Pydantic validator
- **Impact**: Prevents performance issues, sets clear expectations

**✅ 6. Result Structure** (RESOLVED)
- **Solution**: Simplified to `list[str]` (just text chunks)
- **Decision**: No complex metadata per chunk (scores, source, etc.)
- **Impact**: Cleaner, simpler comparison logic

### Remaining Open Issues (Address in Planning)

**1. Error Handling Strategy**
- Need exception hierarchy (ConfigError, RunError, ComparisonError, etc.)
- What errors can each operation raise?
- How to handle partial failures gracefully?

**2. Secrets Management**
- How are secrets loaded from env vars?
- Support for .env files?
- Validation that required secrets exist before running?

**3. Concurrency Model**
- Parallel query execution within a run?
- Thread safety for file I/O?
- Progress reporting mechanism?

**4. Validation & Constraints**
- Domain name format validation
- System config validation (tool-specific schemas?)
- Relationship integrity checks (domain/system/query-set must exist)

**5. Tool Registry**
- How to register new tools/systems?
- Tool discovery mechanism?
- Plugin system for custom tools?

### Resolved Open Questions

1. **Tool Interface**: ✅ `search(query, top_k) -> list[str]`
2. **Storage Backend**: ✅ File system only, no abstraction
3. **Large Query Sets**: ✅ 1000 query limit enforced
4. **CLI Scope**: ✅ Only run and compare commands
5. **Storage Migration**: ✅ Not needed (file-based only)
6. **Multi-tenancy**: ✅ Single user (file-based)
7. **Pagination**: ✅ Not needed (1000 query limit)

### Remaining Open Questions

1. **Run Immutability**: Should runs be immutable once created? (Probably yes)
2. **Versioning**: How to version systems/query sets? (Git?)
3. **Comparison N-way**: Support comparing >2 runs? (Start with 2, extend later)
4. **Query Metadata**: Individual query metadata (difficulty, category)? (Future)
5. **Progress Reporting**: How to show progress during long runs? (Callbacks? Events?)

## Next Steps (SPIDER-SOLO)

1. **Specification** ✓ (this document - after self-review)
2. **Planning**: Create implementation plan (address critical gaps)
3. **Implementation**: Execute in phases
4. **Defense**: Write comprehensive tests
5. **Evaluation**: Code review
6. **Reflection**: Update architecture docs
