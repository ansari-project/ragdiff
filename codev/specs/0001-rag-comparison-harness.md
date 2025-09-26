# Specification: RAG Comparison Test Harness

## Problem Analysis

### Current State
- Ansari Backend uses Mawsuah tool (Vectara-based) for Islamic jurisprudence search
- New RAG system "goodmem" available via goodmem-client library
- No systematic way to compare performance between RAG systems
- Decision to adopt new system based on subjective evaluation

### Desired State
- Data-driven comparison framework for RAG systems
- Quantifiable metrics for relevance, latency, and quality
- Side-by-side evaluation capability
- Clear migration path if goodmem proves superior
- Reusable testing infrastructure for future RAG evaluations

### Stakeholders
- **Development Team**: Need clear technical comparison
- **Product Team**: Need quality and performance metrics
- **End Users**: Will benefit from better search results
- **Operations**: Need to understand resource implications

### Constraints
- Must maintain compatibility with Ansari's SearchVectara interface
- Test repository separate from production code
- Minimal dependencies to reduce complexity
- 2-4 day implementation timeframe
- No production data exposure

### Assumptions
- goodmem-client Python library is available
- Access to both Mawsuah and goodmem APIs
- SearchVectara base class can be imported
- Environment variables for API credentials

## Solution Exploration

### Approach 1: Adapter Pattern with Normalized Results (RECOMMENDED)
**Design**: Create adapters inheriting from SearchVectara, normalize to common RagResult
- **Pros**:
  - Clean separation of concerns
  - Easy Ansari integration later
  - Extensible for new tools
  - Type-safe interfaces
- **Cons**:
  - Need to map different response formats
  - Potential information loss in normalization
- **Complexity**: Medium
- **Risk**: Low

### Approach 2: Direct Integration Testing
**Design**: Integrate directly into Ansari codebase with feature flags
- **Pros**:
  - Immediate production testing
  - Real usage patterns
- **Cons**:
  - Violates test/prod separation
  - Higher risk of breaking changes
  - Complex rollback
- **Complexity**: High
- **Risk**: High

### Approach 3: External Evaluation Framework
**Design**: Use RAGAS or LangSmith for evaluation
- **Pros**:
  - Rich metrics out of box
  - Industry standard tools
- **Cons**:
  - Heavy dependencies
  - Less control
  - Learning curve
- **Complexity**: Medium
- **Risk**: Medium

## Technical Design

### Architecture Overview
```
rag-comparison-harness/
├── src/
│   ├── adapters/
│   │   ├── base.py          # BaseRagTool(SearchVectara)
│   │   ├── goodmem.py       # GoodmemAdapter
│   │   └── mawsuah.py       # MawsuahAdapter
│   ├── core/
│   │   ├── models.py        # RagResult, ComparisonResult
│   │   ├── comparator.py    # Comparison logic
│   │   ├── metrics.py       # Metric calculations
│   │   └── runner.py        # Batch execution
│   └── cli/
│       └── compare_rag.py   # CLI interface
├── configs/
│   └── tools.yaml           # Tool configurations
├── outputs/                 # Results storage
├── tests/
└── requirements.txt
```

### Key Interfaces

```python
# Base adapter matching SearchVectara signature
class BaseRagTool(SearchVectara):
    def run(self, query: str, **kwargs) -> dict:
        """Execute search - matches SearchVectara.run()"""

    def format_as_tool_result(self, results: dict) -> str:
        """Format for Ansari compatibility"""

# Normalized result structure
@dataclass
class RagResult:
    id: str
    text: str
    score: float
    source: Optional[str]
    metadata: Optional[dict]
    latency_ms: Optional[float]
```

### Critical Implementation Details
1. **Method Alignment**: Must use `run()` not `search()` to match SearchVectara
2. **Dual Methods**: Implement both `run()` and `format_as_tool_result()`
3. **Response Normalization**: Handle different API response structures
4. **Async Handling**: Support if goodmem is async
5. **Config Isolation**: Separate test/prod configurations

## Success Criteria

### Functional Requirements
- [ ] Both adapters successfully query their respective systems
- [ ] Identical queries produce comparable results
- [ ] Side-by-side output displays correctly
- [ ] Batch processing handles 100+ queries
- [ ] Results export to JSONL/CSV

### Performance Requirements
- [ ] Single query comparison < 5 seconds
- [ ] Batch of 100 queries < 5 minutes
- [ ] Memory usage < 500MB
- [ ] Graceful handling of API rate limits

### Quality Metrics
- [ ] Overlap@k metric computed accurately
- [ ] Latency tracked per tool (p50, p95)
- [ ] Rank correlation calculated for shared results
- [ ] Error rates logged and reported

### Integration Requirements
- [ ] Adapters work with Ansari's SearchVectara
- [ ] CLI mirrors use_tools.py interface
- [ ] Environment-based configuration
- [ ] No hardcoded credentials

## Comparison Metrics

### Core Metrics (MVP)
1. **Overlap@k**: Jaccard similarity of top-k results
2. **Latency**: Response time percentiles (p50, p95)
3. **Availability**: Success/failure rates
4. **Result Count**: Number of results returned

### Advanced Metrics (Future)
1. **Rank Correlation**: Kendall's tau for shared documents
2. **nDCG@k**: If relevance labels available
3. **Source Congruence**: LLM-judged answer quality
4. **Cost**: API usage costs if available

## Open Questions

### Critical (Blocks Progress)
1. What is the exact goodmem-client API structure?
2. Are there rate limits on either API?
3. Is goodmem synchronous or asynchronous?

### Important (Affects Design)
1. Should we support custom scoring functions?
2. How to handle pagination for large result sets?
3. What constitutes a "fair" comparison between different scoring systems?

### Nice-to-Know (Optimization)
1. Can we cache results for repeated queries?
2. Should we add a web UI later?
3. Integration with CI/CD pipelines?

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Schema Mismatch | High | Create flexible normalizers with fallbacks |
| Rate Limiting | Medium | Implement exponential backoff, request queuing |
| Credential Exposure | High | Use env vars, never commit secrets, .env.example |
| Production Data Access | High | Separate configs, validation checks |
| Async/Sync Mismatch | Medium | Provide sync wrappers for async operations |

## Implementation Phases

### Phase 1: Core Infrastructure (Day 1)
- Set up project structure
- Implement BaseRagTool
- Create RagResult model
- Basic configuration management

### Phase 2: Adapters (Day 1-2)
- Implement MawsuahAdapter
- Implement GoodmemAdapter
- Response normalization
- Error handling

### Phase 3: Comparison Engine (Day 2)
- Comparator implementation
- Basic metrics (overlap, latency)
- Result formatting

### Phase 4: CLI & Output (Day 2-3)
- CLI interface (like use_tools.py)
- Side-by-side display
- JSONL/CSV export
- Batch processing

### Phase 5: Testing & Documentation (Day 3)
- Unit tests for adapters
- Integration tests
- Documentation
- Example queries

## Path to Production

1. **Test Phase**: Run in isolated environment
2. **Validation**: Compare with manual testing results
3. **Integration Prep**: Package as library
4. **Ansari Integration**: Import adapters into Ansari
5. **Migration**: Gradual rollout with feature flags

## Consultation Log

### Initial Analysis (Claude)
- Analyzed SPIDER protocol requirements
- Reviewed Ansari tools structure
- Identified SearchVectara interface requirements

### GPT-5 Review (For Stance)
- Strong support for adapter pattern (8/10 confidence)
- Detailed architecture proposal with file structure
- Emphasized extensibility and registry pattern
- Recommended JSONL/CSV outputs for reproducibility

### Gemini Pro Review (Neutral Stance)
- Validated approach as industry best practice (9/10 confidence)
- Stressed importance of metrics definition
- Suggested golden query set creation
- Advocated for minimal initial implementation

### Deep Analysis (O3-mini)
- Identified critical interface alignment issues
- Highlighted async/sync considerations
- Emphasized configuration isolation needs
- Validated overall architecture approach

## Decision

Proceed with **Approach 1: Adapter Pattern** based on unanimous expert agreement and high confidence scores (8-9/10) from all consulted models.