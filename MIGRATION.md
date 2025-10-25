# Migration Guide: v1.x → v2.0

This guide helps you migrate from RAGDiff v1.x (adapter-based) to v2.0 (domain-based).

## Overview

RAGDiff v2.0 is a complete architectural rewrite. **There is no backwards compatibility** with v1.x. The v2.0 architecture is fundamentally different and provides better reproducibility and organization.

## Key Differences

| Aspect | v1.x | v2.0 |
|--------|------|------|
| Architecture | Adapter-based | Domain-based |
| CLI Commands | `query`, `batch`, `compare` | `run`, `compare` |
| Configuration | YAML config files | Domain directories |
| Reproducibility | None | Full config snapshots |
| Organization | Flat | Hierarchical by domain |
| Run Storage | Not stored | Stored as JSON |

## Migration Steps

### 1. Identify Your Domains

Organize your work into domains (problem areas). Each domain will have its own directory.

**Example v1.x usage:**
```bash
# v1.x: All queries mixed together
uv run ragdiff query "tafsir query" --tool vectara
uv run ragdiff query "legal query" --tool vectara
```

**v2.0 equivalent:**
```bash
# v2.0: Separate domains
domains/tafsir/     # Islamic tafsir domain
domains/legal/      # Legal documents domain
```

### 2. Create Domain Structure

For each domain, create the directory structure:

```bash
mkdir -p domains/my-domain/{systems,query-sets,runs,comparisons}
```

### 3. Convert Configuration Files

**v1.x config** (`configs/tools.yaml`):
```yaml
tools:
  vectara:
    api_key_env: VECTARA_API_KEY
    corpus_id: ${VECTARA_CORPUS_ID}
    timeout: 30
```

**v2.0 equivalent:**

Domain config (`domains/my-domain/domain.yaml`):
```yaml
name: my-domain
description: My domain description
evaluator:
  model: gpt-4
  temperature: 0.0
  prompt_template: |
    Compare these RAG results...
```

System config (`domains/my-domain/systems/vectara-default.yaml`):
```yaml
name: vectara-default
tool: vectara
config:
  api_key: ${VECTARA_API_KEY}
  corpus_id: ${VECTARA_CORPUS_ID}
  timeout: 30
```

### 4. Convert Query Files

**v1.x** (`inputs/queries.txt`):
```
Query 1
Query 2
Query 3
```

**v2.0** (`domains/my-domain/query-sets/test-queries.txt`):
```
Query 1
Query 2
Query 3
```

Same format, just moved to domain-specific location.

### 5. Update CLI Commands

#### Query Command

**v1.x:**
```bash
uv run ragdiff query "What is RAG?" --tool vectara --top-k 5
```

**v2.0:**
```bash
# First, add query to query set file
echo "What is RAG?" >> domains/my-domain/query-sets/test-queries.txt

# Then run
uv run ragdiff run my-domain vectara-default test-queries
```

#### Batch Command

**v1.x:**
```bash
uv run ragdiff batch inputs/queries.txt \
  --config configs/tools.yaml \
  --output-dir results/
```

**v2.0:**
```bash
# Queries should be in domain query set
uv run ragdiff run my-domain vectara-default test-queries

# Results automatically saved to domains/my-domain/runs/
```

#### Compare Command

**v1.x:**
```bash
uv run ragdiff compare results/ --output evaluation.jsonl
```

**v2.0:**
```bash
# Compare runs by ID
uv run ragdiff compare my-domain <run-id-1> <run-id-2>
```

## Configuration Mapping

### Vectara

**v1.x:**
```yaml
vectara:
  api_key_env: VECTARA_API_KEY
  corpus_id: ${VECTARA_CORPUS_ID}
```

**v2.0:**
```yaml
name: vectara-default
tool: vectara
config:
  api_key: ${VECTARA_API_KEY}
  corpus_id: ${VECTARA_CORPUS_ID}
  timeout: 30
```

### MongoDB

**v1.x:**
```yaml
mongodb:
  api_key_env: MONGODB_URI
  options:
    database: my_db
    collection: docs
```

**v2.0:**
```yaml
name: mongodb-local
tool: mongodb
config:
  connection_uri: ${MONGODB_URI}
  database: my_db
  collection: docs
  index_name: vector_index
  embedding_model: all-MiniLM-L6-v2
```

### Agentset

**v1.x:**
```yaml
agentset:
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
```

**v2.0:**
```yaml
name: agentset-prod
tool: agentset
config:
  api_token: ${AGENTSET_API_TOKEN}
  namespace_id: ${AGENTSET_NAMESPACE_ID}
  rerank: true
  timeout: 60
```

## What's Removed

The following v1.x features are removed in v2.0:

- ❌ `query` command (use `run` with query sets instead)
- ❌ `batch` command (use `run` instead)
- ❌ `list-tools` command (not needed)
- ❌ `validate-config` command (validation happens automatically)
- ❌ `quick-test` command (not needed)
- ❌ Library API functions (`query()`, `compare()`, `run_batch()`)
- ❌ Adapter variants in single config file (create separate system configs)

## What's New

v2.0 adds several new features:

- ✅ Domain-based organization
- ✅ Run storage and reproducibility
- ✅ Config snapshots in runs
- ✅ Run ID-based comparison
- ✅ Multi-provider LLM support via LiteLLM
- ✅ Progress bars and rich CLI output
- ✅ Multiple output formats (table, json, markdown)
- ✅ Per-query evaluation with detailed analysis

## Example Migration

### Before (v1.x)

```bash
# Directory structure
ragdiff/
├── configs/
│   └── tools.yaml
├── inputs/
│   └── queries.txt
└── results/  # Output

# Commands
uv run ragdiff batch inputs/queries.txt --config configs/tools.yaml --output-dir results/
uv run ragdiff compare results/ --output evaluation.jsonl
```

### After (v2.0)

```bash
# Directory structure
ragdiff/
└── domains/
    └── my-domain/
        ├── domain.yaml
        ├── systems/
        │   ├── vectara-default.yaml
        │   └── mongodb-local.yaml
        ├── query-sets/
        │   └── test-queries.txt
        ├── runs/  # Auto-created
        └── comparisons/  # Auto-created

# Commands
uv run ragdiff run my-domain vectara-default test-queries
uv run ragdiff run my-domain mongodb-local test-queries
uv run ragdiff compare my-domain <run-id-1> <run-id-2>
```

## Recommendations

1. **Start Fresh**: Don't try to preserve v1.x configs. Create new v2.0 domain structures.

2. **One Domain at a Time**: Migrate one problem area (domain) at a time.

3. **Test Incrementally**: Create a small test domain first to verify everything works.

4. **Use Git**: Track your domain configurations in version control.

5. **Leverage Reproducibility**: Use run snapshots to track system changes over time.

## Getting Help

- Check the [README.md](README.md) for v2.0 documentation
- Check [CLAUDE.md](CLAUDE.md) for developer instructions
- Run `uv run ragdiff --help` for CLI help
- Run `uv run ragdiff run --help` or `uv run ragdiff compare --help` for command-specific help

## Summary

v2.0 is a complete rewrite. You cannot simply update imports or command names. You must:

1. Create domain directories
2. Move configs to domain-specific system configs
3. Move queries to domain query sets
4. Use new `run` and `compare` commands
5. Adapt to run ID-based workflow

The effort is worth it: v2.0 provides much better reproducibility, organization, and systematic RAG development capabilities.
