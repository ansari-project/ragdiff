# TICK Specification: Agentset Adapter for RAGDiff

## Metadata
- **ID**: 0003-agentset-adapter
- **Protocol**: TICK
- **Created**: 2025-10-19
- **Status**: in-progress

## Task Description
Add Agentset as a supported RAG system in RAGDiff, enabling side-by-side comparison with Vectara and Goodmem. Agentset is a RAG-as-a-Service platform that provides managed document ingestion and retrieval with its own S3-compatible storage.

## Scope

### In Scope
- Create `AgentsetAdapter` class implementing `BaseRagTool` interface
- Add Agentset SDK search/query integration
- Register adapter in the factory
- Add Agentset configuration support in YAML configs
- Update documentation with Agentset examples
- Add comprehensive tests for Agentset adapter

### Out of Scope
- Document ingestion/upload functionality (already implemented in ../indexing project)
- Migration of existing data from Vectara/Goodmem to Agentset
- Performance optimization for large-scale queries
- Custom embedding model configuration

## Success Criteria
- [ ] `AgentsetAdapter` class created in `src/adapters/agentset.py`
- [ ] Adapter implements all `BaseRagTool` interface methods correctly
- [ ] Search returns `RagResult` objects with proper metadata
- [ ] Adapter handles Agentset SDK `.data` attribute pattern correctly
- [ ] Registered in `src/adapters/factory.py`
- [ ] Configuration examples added to `configs/tafsir.yaml` and `configs/mawsuah.yaml`
- [ ] Tests added to `tests/test_agentset_adapter.py`
- [ ] README updated with Agentset usage examples
- [ ] All existing tests continue to pass

## Constraints
- Must follow fail-fast principles (no fallbacks)
- Must use uv package manager (agentset>=0.4.0 already installed)
- Must maintain existing adapter interface
- Must handle Agentset SDK response pattern: all responses wrap data in `.data` attribute
- Environment variables: `AGENTSET_API_TOKEN` and `AGENTSET_NAMESPACE_ID`

## Assumptions
- Agentset namespace already has documents ingested (via ../indexing project)
- Agentset SDK v0.4.0+ provides `search.execute()` method for queries
- Search returns list of `SearchData` objects with text, score, and metadata
- Agentset handles embedding and retrieval infrastructure

## Implementation Approach

### 1. Create Agentset Adapter (`src/adapters/agentset.py`)

The adapter will:
1. Initialize Agentset client with API token and namespace ID
2. Implement `search()` method using `client.search.execute()`
3. Convert Agentset `SearchData` objects to `RagResult` format
4. Handle the `.data` attribute pattern correctly
5. Extract metadata from search results

**Key Implementation Details:**
- Use `client.search.execute(query=query, top_k=top_k)` for searches
- Response returns `List[SearchData]` objects
- Each `SearchData` has `.data` attribute containing actual data
- Map Agentset fields to `RagResult`: text, score, metadata, source

### 2. Register in Factory (`src/adapters/factory.py`)

```python
from .agentset import AgentsetAdapter

ADAPTER_REGISTRY["agentset"] = AgentsetAdapter
```

### 3. Add Configuration Support

Add to `configs/tafsir.yaml`:
```yaml
agentset:
  api_key_env: AGENTSET_API_TOKEN
  namespace_id_env: AGENTSET_NAMESPACE_ID
  timeout: 60
  default_top_k: 10
```

### 4. Testing Strategy

Create `tests/test_agentset_adapter.py` with:
- Mock Agentset client responses
- Test `.data` attribute handling
- Test search result conversion to `RagResult`
- Test error handling for missing credentials
- Test top_k parameter handling

## API Reference

### Agentset Search Method Signature
```python
client.search.execute(
    query: str,
    top_k: Optional[float] = 10,
    include_metadata: Optional[bool] = True,
    mode: Optional[Literal['semantic', 'keyword']] = 'semantic',
    # ... other parameters
) -> List[SearchData]
```

### SearchData Structure
Based on SDK exploration, each `SearchData` object has:
- `.data` attribute containing the actual search result
- Fields likely include: text/content, score, metadata, document_id

## Risks

| Risk | Mitigation |
|------|------------|
| Agentset SDK `.data` pattern causing AttributeError | Review Agentset docs, use consistent `.data.field` pattern |
| SearchData structure unclear | Inspect actual responses, check SDK source code |
| Missing environment variables | Validate config at startup, fail fast with clear error |
| Different metadata schema than Vectara/Goodmem | Map available fields, document differences |

## Testing Approach

### Test Scenarios
1. **Happy path**: Query returns results successfully
2. **Empty results**: Query returns no matches
3. **SDK response pattern**: Verify `.data` attribute handling
4. **Top-k parameter**: Verify limit parameter works correctly
5. **Metadata extraction**: Verify metadata is properly extracted
6. **Error scenarios**: Missing credentials, network errors, invalid queries

### Manual Testing
```bash
# Configure environment
export AGENTSET_API_TOKEN=your_token
export AGENTSET_NAMESPACE_ID=your_namespace

# Test with tafsir config
uv run python -m src.cli compare "What is tawhid?" --config configs/tafsir.yaml --tool agentset

# Compare Agentset vs Vectara
uv run python -m src.cli compare "Islamic inheritance law" --tool agentset --tool tafsir
```

## Dependencies
- `agentset>=0.4.0` (already installed)
- Environment variables: `AGENTSET_API_TOKEN`, `AGENTSET_NAMESPACE_ID`

## Documentation Updates
- Add Agentset to README "Adding New RAG Tools" section
- Add Agentset configuration example
- Update comparison examples to include Agentset

## Notes
- Agentset provides the full storage infrastructure (S3-compatible)
- Documents are ingested via ../indexing project using batch upload
- Focus on retrieval/search only, not ingestion
- Follow the same adapter pattern as Vectara and Goodmem for consistency
