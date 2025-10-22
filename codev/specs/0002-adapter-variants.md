# TICK Spec: Adapter Variants Support

**ID**: 0002
**Created**: 2025-10-19
**Status**: ✅ Completed
**Protocol**: TICK

---

## T - Task/Specification

### Problem
Currently, comparing different configurations of the same RAG tool (e.g., "agentset with rerank" vs "agentset without rerank") requires:
1. Hardcoding variant names in the adapter factory
2. Manually registering each variant
3. Limited flexibility for A/B testing different configurations

### Solution
Enable flexible adapter variants through YAML configuration by:
1. Adding an optional `adapter` field to specify which adapter class to use
2. Using the YAML key as the display name (not the adapter class name)
3. Supporting custom `options` dict for adapter-specific configuration
4. Maintaining backward compatibility with existing configs

### Example Use Case
```yaml
# Compare Agentset with different reranking settings
agentset-rerank-on:
  adapter: agentset
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
  options:
    rerank: true

agentset-rerank-off:
  adapter: agentset
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
  options:
    rerank: false

# Compare Vectara with different corpora
tafsir-corpus:
  adapter: vectara
  corpus_id: tafsir_v1

mawsuah-corpus:
  adapter: vectara
  corpus_id: mawsuah_v1
```

### Success Criteria
1. Can define multiple variants of same adapter in YAML
2. Each variant appears with its YAML key name in results
3. Adapters can access custom options from config
4. Backward compatible - existing configs work without changes
5. No factory code changes needed to add new variants

---

## I - Implementation

### Changes Required

#### 1. Update `ToolConfig` (src/ragdiff/core/models.py)
Add new fields:
```python
@dataclass
class ToolConfig:
    name: str  # Display name from YAML key
    api_key_env: str
    adapter: Optional[str] = None  # Adapter class to use
    options: Optional[Dict[str, Any]] = None  # Custom adapter options
    # ... existing fields ...
```

#### 2. Update Config Parser (src/ragdiff/core/config.py)
Parse `adapter` and `options` fields from YAML:
```python
self.tools[tool_name] = ToolConfig(
    name=tool_name,  # YAML key becomes name
    adapter=tool_dict.get("adapter", tool_name),  # Default to name
    options=tool_dict.get("options"),  # Optional custom config
    # ... other fields ...
)
```

#### 3. Update Factory (src/ragdiff/adapters/factory.py)
Use `config.adapter` instead of `tool_name`:
```python
def create_adapter(tool_name: str, config: ToolConfig) -> BaseRagTool:
    adapter_name = config.adapter or tool_name  # Backward compat
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {adapter_name}")

    adapter_class = ADAPTER_REGISTRY[adapter_name]
    return adapter_class(config)
```

#### 4. Update AgentsetAdapter (src/ragdiff/adapters/agentset.py)
Support rerank option:
```python
def search(self, query: str, top_k: int = 5):
    # Get rerank setting from options
    rerank = True  # Default
    if self.config.options:
        rerank = self.config.options.get('rerank', True)

    # Pass to SDK (if supported)
    # Note: Need to check if Agentset SDK supports rerank parameter
```

### Files to Modify
- `src/ragdiff/core/models.py` - Add `adapter` and `options` to ToolConfig
- `src/ragdiff/core/config.py` - Parse new fields
- `src/ragdiff/adapters/factory.py` - Use `config.adapter`
- `src/ragdiff/adapters/agentset.py` - Use options for rerank
- `tests/test_adapter_factory.py` - Add variant tests
- `configs/tafsir.yaml` - Add example variants (optional)
- `README.md` - Document variant configuration

---

## C - Check/Testing

### Test Cases

1. **Backward Compatibility**
   - Existing configs without `adapter` field work
   - Tool name defaults to adapter name

2. **Variant Support**
   - Multiple tools using same adapter
   - Each variant has correct display name
   - Options passed to adapter correctly

3. **Factory Tests**
   - Factory uses `config.adapter` field
   - Falls back to tool_name if no adapter field
   - Unknown adapter raises ValueError

4. **Integration Tests**
   - Run comparison with two variants
   - Verify both variants execute correctly
   - Results show correct display names

### Manual Testing
```bash
# Test with agentset variants
uv run rag-compare compare "test query" \
  --tool agentset-rerank \
  --tool agentset-no-rerank \
  --config configs/tafsir.yaml
```

---

## K - Knowledge/Documentation

### Configuration Format
Document in README.md:

```yaml
# Tool variants allow comparing different configurations
# of the same adapter

tool-variant-name:           # Display name (required)
  adapter: adapter_class     # Which adapter to use (optional, defaults to tool name)
  options:                   # Custom options (optional)
    key: value
  # ... standard fields ...
  api_key_env: ENV_VAR
  timeout: 60
```

### Migration Guide
- Existing configs work without changes
- To add variants, just create new YAML entries with `adapter` field
- No code changes needed to add new variants

### Design Rationale
- YAML key = display name (intuitive)
- `adapter` field = which class to use (explicit)
- `options` dict = flexible for any adapter-specific config
- Backward compatible = no breaking changes
