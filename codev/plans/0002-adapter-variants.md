# Implementation Plan: Adapter Variants Support

**ID**: 0002
**Spec**: [0002-adapter-variants.md](../specs/0002-adapter-variants.md)
**Created**: 2025-10-19
**Status**: ✅ Completed

---

## Overview

Enable flexible adapter variants through YAML configuration, allowing users to compare different configurations of the same RAG tool (e.g., "agentset with rerank" vs "agentset without rerank") without modifying code.

## Implementation Steps

### Step 1: Update Data Models
**File**: `src/ragdiff/core/models.py`

Add two new optional fields to `ToolConfig`:
- `adapter: Optional[str]` - Which adapter class to use (defaults to tool name)
- `options: Optional[Dict[str, Any]]` - Custom adapter-specific configuration

**Rationale**: Separating display name (YAML key) from adapter type (adapter field) enables variants.

### Step 2: Update Configuration Parser
**File**: `src/ragdiff/core/config.py`

Parse the new `adapter` and `options` fields from YAML:
```python
self.tools[tool_name] = ToolConfig(
    name=tool_name,  # YAML key becomes display name
    adapter=tool_dict.get("adapter", tool_name),  # Default to name
    options=tool_dict.get("options"),  # Optional custom config
    # ... other fields ...
)
```

**Rationale**: Backward compatible - if no `adapter` field, defaults to tool name.

### Step 3: Update Adapter Factory
**File**: `src/ragdiff/adapters/factory.py`

Change factory to use `config.adapter` instead of `tool_name`:
```python
def create_adapter(tool_name: str, config: ToolConfig) -> BaseRagTool:
    adapter_name = config.adapter or tool_name
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {adapter_name}")

    adapter_class = ADAPTER_REGISTRY[adapter_name]
    return adapter_class(config)
```

**Rationale**: Enables multiple configs to use the same adapter class.

### Step 4: Update Adapters to Use Options
**Files**: Adapters that support configuration options

Example for Agentset adapter:
```python
def search(self, query: str, top_k: int = 5):
    # Get rerank setting from options
    rerank = True  # Default
    if self.config.options:
        rerank = self.config.options.get('rerank', True)

    # Pass to SDK
    results = self.client.search.execute(
        query=query,
        top_k=top_k,
        rerank=rerank  # Use option
    )
```

**Rationale**: Adapters can access variant-specific configuration via `self.config.options`.

### Step 5: Add Tests
**File**: `tests/test_adapter_factory.py`

Test cases:
1. Backward compatibility - configs without `adapter` field
2. Variant support - multiple configs using same adapter
3. Options passing - verify options reach adapter
4. Unknown adapter - raises ValueError

### Step 6: Update Documentation
**File**: `README.md`

Add section on adapter variants with examples:
```yaml
# Compare same adapter with different configurations
vectara-tafsir:
  adapter: vectara
  corpus_id: tafsir_corpus

vectara-mawsuah:
  adapter: vectara
  corpus_id: mawsuah_corpus
```

## Testing Strategy

### Unit Tests
- ToolConfig creation with adapter/options fields
- Config parser handles adapter field
- Factory uses config.adapter correctly
- Factory falls back to tool_name when no adapter field

### Integration Tests
- Load config with variants
- Run comparison with two variants of same adapter
- Verify both execute correctly
- Results show correct display names

### Manual Testing
```bash
# Create test config with variants
cat > test-variants.yaml <<EOF
agentset-rerank:
  adapter: agentset
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
  options:
    rerank: true

agentset-no-rerank:
  adapter: agentset
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
  options:
    rerank: false
EOF

# Test comparison
rag-compare compare "test query" \
  --tool agentset-rerank \
  --tool agentset-no-rerank \
  --config test-variants.yaml
```

## Migration Impact

### Backward Compatibility
✅ **Fully backward compatible**
- Existing configs work without changes
- When `adapter` field is missing, defaults to tool name
- No breaking changes to API

### New Capabilities
- Users can define multiple variants of same adapter
- Each variant can have custom options
- No code changes needed to add new variants

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing configs | HIGH | Default `adapter` to tool name |
| Options not reaching adapters | MEDIUM | Test options passing thoroughly |
| Unknown adapter type | LOW | Fail fast with clear error message |
| Options schema unclear | LOW | Document in adapter docstrings |

## Success Criteria

- [x] `ToolConfig` has `adapter` and `options` fields
- [x] Config parser extracts both fields from YAML
- [x] Factory uses `config.adapter` to select adapter class
- [x] Backward compatible - existing configs work unchanged
- [x] Tests verify variant functionality
- [x] Documentation updated with examples

## Implementation Notes

### Design Decisions
1. **YAML key = display name**: Intuitive for users
2. **adapter field = class selection**: Explicit and flexible
3. **options dict = variant config**: Generic, adapter-specific
4. **Default adapter to name**: Backward compatibility

### Known Limitations
- Adapters must handle missing options gracefully
- Options schema is adapter-specific (not validated centrally)
- No automatic option validation

### Future Enhancements
- Schema validation for adapter options
- Auto-discovery of available options per adapter
- Default option values in adapter registry
