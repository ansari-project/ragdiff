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
- `evaluator`: Evaluator configuration for comparisons
- `metadata`: Optional metadata (tags, owner, created_at, etc.)

**Domain Configuration** (YAML file):
```yaml
# domains/tafsir/domain.yaml
name: tafsir
description: Islamic Tafsir comparison

variables:
  timeout: 30
  max_retries: 3

secrets:
  anthropic_key: ${ANTHROPIC_API_KEY}
  # Secrets are loaded from environment variables
  # Uses ${VAR_NAME} syntax for environment variable substitution
  # Supports .env file in project root or domain directory

evaluator:
  model: claude-3-5-sonnet-20241022
  temperature: 0.0
  prompt_template: |
    You are evaluating RAG system outputs for the query: "{query}"

    Reference answer: {reference}

    System A output:
    {system_a_output}

    System B output:
    {system_b_output}

    Which system provided better results? Rate each on a scale of 0-100 and explain your reasoning.

metadata:
  owner: ansari-project
  created_at: 2025-10-25
```

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
from pydantic import BaseModel, Field
from typing import Any

class RetrievedChunk(BaseModel):
    """A single retrieved text chunk with metadata."""
    content: str  # The actual text content
    score: float | None = None  # Relevance score (if available)
    metadata: dict[str, Any] = Field(default_factory=dict)  # source_id, doc_id, chunk_id, etc.

class System(ABC):
    """A system accepts a query and returns retrieved chunks with metadata."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """
        Execute search and return ranked chunks with metadata.

        Args:
            query: The search query
            top_k: Number of results to return

        Returns:
            List of RetrievedChunk objects, ordered by relevance
        """
        pass
```

**Tool Registry**:
```python
# Tools are registered at module initialization
TOOL_REGISTRY: dict[str, type[System]] = {
    "vectara": VectaraSystem,
    "mongodb": MongoDBSystem,
    "agentset": AgentsetSystem,
}

def get_tool(tool_name: str) -> type[System]:
    """Get tool class by name."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_REGISTRY.keys())}")
    return TOOL_REGISTRY[tool_name]
```

**System Configuration** (YAML file):
```yaml
# domains/tafsir/systems/vectara-mmr.yaml
name: vectara-mmr
tool: vectara  # Which tool class to instantiate
config:
  # API credentials
  api_key: ${VECTARA_API_KEY}
  corpus_id: ${VECTARA_CORPUS_ID}

  # Search settings
  top_k: 5              # Number of results to return
  timeout: 30           # Timeout in seconds per query

  # Tool-specific config
  reranking: mmr
  diversity_bias: 0.3

metadata:
  description: Vectara with MMR reranking
```

**Note**: `top_k` and `timeout` are part of the system configuration. Different systems can have different settings configured in their YAML files.

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
Collection of queries. **Maximum 1000 queries per query set.**

**Internal Representation**:
All queries are loaded into a unified `Query` model with optional reference:
```python
class Query(BaseModel):
    text: str  # The query text
    reference: str | None = None  # Optional reference answer
    metadata: dict[str, Any] = Field(default_factory=dict)  # Future: difficulty, category, etc.
```

**File Format 1: Query Only** (plain text file)
```
What is Islamic inheritance law?
How do we calculate zakat?
What are the pillars of Islam?
```

**File Format 2: Query + Reference** (JSONL file)
```jsonl
{"query": "What is Islamic inheritance law?", "reference": "Inheritance is distributed according to fixed shares..."}
{"query": "How do we calculate zakat?", "reference": "Zakat is 2.5% of wealth held for one lunar year..."}
```

**File Locations**:
- Query-only: `domains/<domain>/query-sets/<name>.txt`
- Query+reference: `domains/<domain>/query-sets/<name>.jsonl`

**Loading**:
Both file formats are parsed into the same internal `Query` model. Text files create `Query(text=line, reference=None)`, while JSONL files create `Query(text=entry["query"], reference=entry.get("reference"))`.

**Constraints**:
- Maximum 1000 queries per query set
- Query set type auto-detected from file extension (.txt vs .jsonl)
- Each query text must be non-empty after stripping whitespace

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
- `system_config`: Snapshot of SystemConfig used (for reproducibility)
- `query_set_snapshot`: Snapshot of QuerySet used (for reproducibility)
- `started_at`: When execution started (ISO 8601 UTC)
- `completed_at`: When execution finished (ISO 8601 UTC)
- `metadata`: Duration, success rate, error count, version info

**Reproducibility**: The Run stores complete snapshots of the system configuration and query set used. This means even if you later modify `vectara-mmr.yaml` or `basic-test.txt`, the historical run remains fully reproducible with the exact config that produced those results.

**Result Structure** (per query):
```python
{
    "query": str,
    "retrieved": list[RetrievedChunk],  # Chunks with metadata (content, score, source_id, etc.)
    "reference": str | None,  # If query_reference type
    "duration_ms": float,
    "error": str | None  # Error message if this query failed
}
```

**File Storage**:
```
domains/<domain>/runs/YYYY-MM-DD/<run-id>.json
```

Runs are organized by date for easier navigation and management. For example:
- `domains/tafsir/runs/2025-10-25/550e8400-e29b-41d4-a716-446655440000.json`
- `domains/tafsir/runs/2025-10-26/660f9511-e29b-41d4-a716-446655440001.json`

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "tafsir",
  "system": "vectara-mmr",
  "query_set": "basic-test",
  "status": "completed",
  "system_config": {
    "name": "vectara-mmr",
    "tool": "vectara",
    "config": {
      "api_key": "${VECTARA_API_KEY}",
      "corpus_id": "${VECTARA_CORPUS_ID}",
      "top_k": 5,
      "timeout": 30,
      "reranking": "mmr",
      "diversity_bias": 0.3
    }
  },
  "query_set_snapshot": {
    "name": "basic-test",
    "domain": "tafsir",
    "type": "query_only",
    "queries": [
      {"text": "What is Islamic inheritance law?", "reference": null},
      {"text": "How do we calculate zakat?", "reference": null}
    ]
  },
  "started_at": "2025-10-25T10:30:00Z",
  "completed_at": "2025-10-25T10:32:15Z",
  "results": [
    {
      "query": "What is Islamic inheritance law?",
      "retrieved": [
        {
          "content": "Inheritance in Islam is governed by fixed shares...",
          "score": 0.95,
          "metadata": {"source_id": "ibn-katheer-v4", "doc_id": "123", "chunk_id": "45"}
        },
        {
          "content": "The Quran establishes clear rules for inheritance distribution...",
          "score": 0.89,
          "metadata": {"source_id": "qurtubi-v2", "doc_id": "456", "chunk_id": "78"}
        }
      ],
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

**Note**: These models are used for type safety, validation, and JSON serialization. Configuration is file-based (YAML), and runs are stored as JSON files.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from abc import ABC, abstractmethod

# ============================================================================
# Core Models
# ============================================================================

class RunStatus(str, Enum):
    """Run execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some queries succeeded, some failed

class RetrievedChunk(BaseModel):
    """A single retrieved text chunk with metadata."""
    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)  # source_id, doc_id, chunk_id, etc.

class Query(BaseModel):
    """A single query with optional reference answer."""
    text: str
    reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator('text')
    @classmethod
    def validate_text_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Query text cannot be empty")
        return v.strip()

# ============================================================================
# Configuration Models
# ============================================================================

class EvaluatorConfig(BaseModel):
    """LLM evaluator configuration for comparisons."""
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    prompt_template: str

class Domain(BaseModel):
    """Domain configuration (loaded from domains/<domain>/domain.yaml)."""
    name: str
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)  # env var names
    evaluator: EvaluatorConfig
    metadata: dict[str, Any] = Field(default_factory=dict)

class SystemConfig(BaseModel):
    """System configuration (loaded from domains/<domain>/systems/<name>.yaml)."""
    name: str
    tool: str  # "vectara", "mongodb", "agentset", etc.
    config: dict[str, Any]  # includes top_k, timeout, and tool-specific config
    metadata: dict[str, Any] = Field(default_factory=dict)

class QuerySet(BaseModel):
    """Query set (loaded from domains/<domain>/query-sets/<name>.{txt,jsonl})."""
    name: str
    domain: str
    queries: list[Query]

    @field_validator('queries')
    @classmethod
    def validate_max_queries(cls, v):
        if len(v) > 1000:
            raise ValueError("Query set cannot exceed 1000 queries")
        if not v:
            raise ValueError("Query set cannot be empty")
        return v

# ============================================================================
# System Interface
# ============================================================================

class System(ABC):
    """Abstract base class for all RAG systems."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Execute search and return ranked chunks with metadata."""
        pass

# ============================================================================
# Run and Result Models
# ============================================================================

class QueryResult(BaseModel):
    """Result for a single query within a run."""
    query: str
    retrieved: list[RetrievedChunk]
    reference: str | None = None
    duration_ms: float
    error: str | None = None

class Run(BaseModel):
    """Run execution result (stored as domains/<domain>/runs/YYYY-MM-DD/<id>.json)."""
    id: UUID = Field(default_factory=uuid4)
    domain: str
    system: str  # system name
    query_set: str  # query set name
    status: RunStatus
    results: list[QueryResult]

    # Snapshots for reproducibility
    system_config: SystemConfig
    query_set_snapshot: QuerySet

    # Timing
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

# ============================================================================
# Comparison Models
# ============================================================================

class EvaluationResult(BaseModel):
    """Evaluation result for comparing multiple runs on a single query."""
    query: str
    reference: str | None
    run_results: dict[str, list[RetrievedChunk]]  # system name -> retrieved chunks
    evaluation: dict[str, Any]  # winner, reasoning, scores

class Comparison(BaseModel):
    """Comparison of multiple runs (stored as domains/<domain>/comparisons/YYYY-MM-DD/<id>.json)."""
    id: UUID = Field(default_factory=uuid4)
    domain: str
    runs: list[UUID]  # run IDs being compared
    evaluations: list[EvaluationResult]
    evaluator_config: EvaluatorConfig  # Snapshot of evaluator used
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
```

## File System Organization

All configuration and data is stored in the file system under a `domains/` directory:

```
domains/
  <domain-name>/
    domain.yaml                    # Domain configuration (with evaluator config)
    .env                           # Optional: domain-specific environment variables

    systems/
      <system-name>.yaml           # System configurations (one per system)

    query-sets/
      <query-set-name>.txt         # Query-only sets
      <query-set-name>.jsonl       # Query+reference sets

    runs/
      YYYY-MM-DD/                  # Date-organized subdirectories
        <run-id>.json              # Run results (auto-generated)

    comparisons/
      YYYY-MM-DD/                  # Date-organized subdirectories
        <comparison-id>.json       # Comparison results (auto-generated)
```

**Configuration Management**:
- Domains, systems, and query sets are managed by editing YAML/text files
- No CLI commands for CRUD operations on these entities
- CLI only supports executing runs and comparisons

**Secrets Management**:
- Environment variables loaded from `.env` file in project root or domain directory
- Uses `python-dotenv` for automatic loading
- Required secrets validated before run execution (fail-fast if missing)
- Example `.env` file:
  ```bash
  VECTARA_API_KEY=your_key_here
  VECTARA_CORPUS_ID=your_corpus_id
  ANTHROPIC_API_KEY=your_key_here
  ```

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
  anthropic_key: \${ANTHROPIC_API_KEY}
EOF

# Create system config
cat > domains/tafsir/systems/vectara-mmr.yaml <<EOF
name: vectara-mmr
tool: vectara
config:
  api_key: \${VECTARA_API_KEY}
  corpus_id: \${VECTARA_CORPUS_ID}
  reranking: mmr
  diversity_bias: 0.3
EOF

# Create query set
cat > domains/tafsir/query-sets/basic-test.txt <<EOF
What is Islamic inheritance law?
How do we calculate zakat?
EOF

# Now use CLI to run and compare
ragdiff run tafsir vectara-mmr basic-test
```

## Library API

The Python library provides functions for loading configuration and executing runs. These functions can be used both:
1. **Internally**: By the CLI commands
2. **Externally**: By users who want to integrate RAGDiff into their own Python code (e.g., Jupyter notebooks, custom scripts, automation)

**Use Cases**:
- Programmatic access to run experiments from Python
- Integration with existing workflows
- Custom analysis and visualization
- Automation and batch processing

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
    query_set="basic-test"
)
# Returns Run object and saves to domains/tafsir/runs/<run-id>.json
# Uses top_k and timeout from system config
```

### Comparison

```python
# Compare runs (used by CLI)
from ragdiff.comparator import compare_runs

comparison = compare_runs(
    domain="tafsir",
    run_ids=["550e8400-...", "660f9511-..."]
)
# Returns Comparison object and saves to domains/tafsir/comparisons/<comparison-id>.json
# Uses evaluator config from domain.yaml
```

## CLI Design

The CLI only supports two operations: **running experiments** and **comparing results**. All configuration (domains, systems, query sets) is managed by editing YAML/text files directly.

### Run Command

Execute a query set against a system and save the results.

```bash
# Basic usage
ragdiff run <domain> <system> <query-set> [OPTIONS]

# Execute query set (uses system's configured top_k and timeout)
ragdiff run tafsir vectara-mmr basic-test

# Show progress
ragdiff run tafsir vectara-mmr basic-test --verbose

# Options:
#   --verbose          Show progress during execution
#   --dry-run          Validate config without executing
#   --output PATH      Custom output path (default: auto-generated in domains/<domain>/runs/YYYY-MM-DD/)
```

**Output**:
- Creates run JSON file in `domains/<domain>/runs/<run-id>.json`
- Prints run ID to stdout for use in comparisons
- Shows summary statistics (total queries, success rate, duration)

**Example**:
```bash
$ ragdiff run tafsir vectara-mmr basic-test
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

Compare two or more runs using LLM evaluation. Domain is required to ensure runs are from the same context.

```bash
# Basic usage (requires domain for context)
ragdiff compare --domain <domain> <run-id-1> <run-id-2> [OPTIONS]

# Compare two runs (uses domain's evaluator config)
ragdiff compare --domain tafsir 550e8400 660f9511

# Short UUID prefixes work (as long as they're unique within the domain)
ragdiff compare --domain tafsir 550e 660f

# Use aliases for recent runs
ragdiff compare --domain tafsir @latest @2  # compare latest run with 2nd most recent

# Different output format
ragdiff compare --domain tafsir 550e 660f --format markdown

# Options:
#   --domain TEXT       Required: domain name for context
#   --format TEXT       Output format: json, markdown, table (default: json)
#   --output PATH       Custom output path (default: auto-generated)
#   --verbose          Show progress during evaluation
```

**UUID Handling**:
- Full UUIDs: `550e8400-e29b-41d4-a716-446655440000`
- Short prefixes: `550e8400` or even `550e` (as long as unique within domain)
- Aliases: `@latest`, `@2`, `@3` (reference recent runs by recency)

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

### Resolved Issues (Agent Reviews + User Feedback)

**✅ 1. System.search API Too Simple** (CRITICAL - Codex/Pro Reviews)
- **Problem**: Returning `list[str]` discarded scores, source IDs, and other metadata needed for evaluation
- **Solution**: Created `RetrievedChunk` model with content, score, and metadata fields
- **Impact**: Enables proper evaluation with provenance tracking

**✅ 2. Missing Configuration Snapshotting** (CRITICAL - Codex/Pro Reviews)
- **Problem**: Runs referenced systems by name only, losing reproducibility if configs changed
- **Solution**: Added `system_config` and `query_set_snapshot` fields to Run model
- **Impact**: Full reproducibility - can see exact config that produced results

**✅ 3. No Tool Registry Pattern** (CRITICAL - Codex/Pro Reviews)
- **Problem**: No defined mechanism for mapping tool names to System classes
- **Solution**: Added `TOOL_REGISTRY` dictionary and `get_tool()` function
- **Impact**: Clear tool discovery and registration pattern

**✅ 4. QuerySet Union Type** (Codex/Pro Reviews)
- **Problem**: Using `list[str] | list[dict[str, str]]` was awkward and unclear
- **Solution**: Created unified `Query` model with text and optional reference
- **Impact**: Type-safe, clean internal representation

**✅ 5. Missing Evaluator Config** (User Comment Line 538)
- **Problem**: No way to configure LLM evaluator per domain
- **Solution**: Added `evaluator` section to domain.yaml with structured `EvaluatorConfig`
- **Impact**: Domain-specific evaluation prompts and model settings

**✅ 6. top_k/timeout in Wrong Place** (User Comments 480-482)
- **Problem**: These were CLI flags instead of system config
- **Solution**: Moved to system config YAML files
- **Impact**: Different systems can have different settings, cleaner CLI

**✅ 7. Run Config Field** (User Comment Line 150)
- **Problem**: Run had redundant config field alongside snapshots
- **Solution**: Removed config field, kept only system_config and query_set_snapshot
- **Impact**: Cleaner model, single source of truth for reproducibility

**✅ 8. Library API Scope Unclear** (User Comment Line 409)
- **Problem**: Spec said "internal only" but should be public
- **Solution**: Clarified API serves both internal (CLI) and external (user code) use cases
- **Impact**: Clear that users can import and use library functions directly

**✅ 9. Environment Variable Syntax** (User Feedback)
- **Problem**: Used `VECTARA_API_KEY` instead of `${VECTARA_API_KEY}`
- **Solution**: Updated all env var references to use `${VAR_NAME}` syntax throughout
- **Impact**: Consistent with standard env var substitution patterns

**✅ 10. Override Patterns** (User Feedback)
- **Problem**: CLI had --top-k, --timeout, --model, --temperature override flags
- **Solution**: Removed all override options - config is immutable per run
- **Impact**: Simpler CLI, clearer mental model, true config snapshots

**✅ 11. CLI Missing Domain Context** (Codex/Pro Reviews)
- **Problem**: Compare command didn't require domain, could compare cross-domain
- **Solution**: Made --domain required for compare command
- **Impact**: Ensures runs are from same context

**✅ 12. UUID Usability** (Codex/Pro Reviews)
- **Problem**: Full UUIDs are cumbersome to type
- **Solution**: Added support for short prefixes and aliases (@latest, @2)
- **Impact**: Much better CLI ergonomics

**✅ 13. File Organization** (Codex/Pro Reviews)
- **Problem**: Flat runs/ directory would become cluttered over time
- **Solution**: Organized runs and comparisons by date (YYYY-MM-DD subdirectories)
- **Impact**: Easier navigation and management

**✅ 14. Secrets Management** (Codex/Pro Reviews)
- **Problem**: Unclear how environment variables are loaded
- **Solution**: Documented python-dotenv support, .env file locations, validation
- **Impact**: Clear secrets handling pattern

### Resolved Open Questions

1. **Tool Interface**: ✅ `search(query, top_k) -> list[RetrievedChunk]` with metadata
2. **Storage Backend**: ✅ File system only, no abstraction
3. **Large Query Sets**: ✅ 1000 query limit enforced
4. **CLI Scope**: ✅ Only run and compare commands, no overrides
5. **Storage Migration**: ✅ Not needed (file-based only)
6. **Multi-tenancy**: ✅ Single user (file-based)
7. **Pagination**: ✅ Not needed (1000 query limit)
8. **Run Immutability**: ✅ Runs are immutable (config snapshots prove this)
9. **Override Pattern**: ✅ No overrides - config is immutable per run

### Remaining Open Issues (Address in Planning)

**1. Error Handling Strategy**
- Need exception hierarchy (ConfigError, RunError, ComparisonError, etc.)
- What errors can each operation raise?
- How to handle partial failures gracefully?

**2. Concurrency Model**
- Parallel query execution within a run?
- Thread safety for file I/O?
- Progress reporting mechanism?

**3. Validation & Constraints**
- Domain name format validation
- System config validation (tool-specific schemas?)
- Relationship integrity checks (domain/system/query-set must exist)

**4. Secrets Validation**
- When to validate required secrets (startup vs run-time)?
- Clear error messages for missing secrets

**5. Tool Registry Implementation**
- How tools register themselves (decorator? module import?)
- Handling tool initialization with config

### Future Enhancements (Not for v2.0.0)

1. **Versioning**: How to version systems/query sets? (Git-based approach?)
2. **Comparison N-way**: Support comparing >2 runs? (Start with 2, extend later)
3. **Query Metadata**: Individual query metadata (difficulty, category)? (Future)
4. **Progress Reporting**: How to show progress during long runs? (Callbacks? Events?)

## Next Steps (SPIDER-SOLO)

1. **Specification** ✓ (this document - after self-review)
2. **Planning**: Create implementation plan (address critical gaps)
3. **Implementation**: Execute in phases
4. **Defense**: Write comprehensive tests
5. **Evaluation**: Code review
6. **Reflection**: Update architecture docs
