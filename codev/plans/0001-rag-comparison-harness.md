# Implementation Plan: RAG Comparison Test Harness

## Overview
Transform the approved specification into a working RAG comparison tool that emphasizes subjective quality evaluation through human-friendly displays and Claude 4.1 Opus analysis.

## Success Metrics
- **Done**: Working CLI that compares goodmem and Mawsuah results
- **Done**: Side-by-side display with color-coded differences
- **Done**: Claude 4.1 Opus evaluation integrated and producing insights
- **Done**: HTML export functionality for sharing
- **Done**: All adapters compatible with SearchVectara interface

## Phase Definition

### Phase 1: Core Infrastructure and Base Adapter
**Objective**: Establish foundational components and adapter pattern
**Dependencies**: None
**Deliverables**:
- Project structure created
- BaseRagTool class inheriting from SearchVectara
- RagResult and ComparisonResult dataclasses
- Basic configuration management with YAML
- Environment variable handling for credentials

**Evaluation Criteria**:
- BaseRagTool properly extends SearchVectara with run() and format_as_tool_result()
- Configuration loads from YAML and environment
- Type hints and dataclasses properly defined
- Basic error handling in place

**Commit**: Single commit after validation

### Phase 2: Tool Adapters Implementation
**Objective**: Create working adapters for both RAG systems
**Dependencies**: Phase 1 (BaseRagTool and models)
**Deliverables**:
- MawsuahAdapter fully implemented
- GoodmemAdapter with goodmem-client integration
- Response normalization to RagResult format
- Error handling and retry logic
- Async/sync compatibility layer if needed

**Evaluation Criteria**:
- Both adapters successfully query their respective APIs
- Response normalization maintains essential information
- Graceful error handling with meaningful messages
- Unit tests for each adapter

**Commit**: Single commit after both adapters tested

### Phase 3: Comparison and Evaluation Engine
**Objective**: Implement comparison logic and LLM evaluation
**Dependencies**: Phase 2 (Working adapters)
**Deliverables**:
- Comparator class for orchestrating comparisons
- Claude 4.1 Opus integration in evaluator.py
- Structured prompt engineering for evaluation
- JSON output format for LLM insights
- Basic performance metrics collection

**Evaluation Criteria**:
- Claude 4.1 Opus successfully evaluates result pairs
- Evaluation produces structured JSON with insights
- Performance metrics (latency, errors) tracked
- Error handling for LLM API failures

**Commit**: Single commit after LLM evaluation working

### Phase 4: Human-Friendly Display System
**Objective**: Create compelling visual comparison interface
**Dependencies**: Phase 3 (Comparison engine)
**Deliverables**:
- Rich console display with side-by-side layout
- Color-coded highlighting of differences
- Synchronized scrolling simulation in terminal
- HTML export with proper styling
- Progressive disclosure (expandable sections)

**Evaluation Criteria**:
- Console output is readable and well-formatted
- HTML export renders correctly in browsers
- Color coding effectively highlights differences
- Display handles various result lengths gracefully

**Commit**: Single commit after display system complete

### Phase 5: CLI Interface and Batch Processing
**Objective**: Create user-facing CLI similar to use_tools.py
**Dependencies**: Phase 4 (Display system)
**Deliverables**:
- CLI with argparse/typer for command parsing
- Single query mode with immediate display
- Batch processing from file input
- Progress tracking for batch operations
- Output to JSONL for analysis

**Evaluation Criteria**:
- CLI matches use_tools.py interaction patterns
- Batch processing handles 100+ queries
- Progress indicators work correctly
- JSONL output is valid and complete

**Commit**: Single commit after CLI fully functional

### Phase 6: Testing and Documentation
**Objective**: Ensure reliability and usability
**Dependencies**: Phase 5 (Complete system)
**Deliverables**:
- Unit tests for all modules
- Integration tests for end-to-end flow
- Example queries and expected outputs
- README with setup and usage instructions
- Configuration examples

**Evaluation Criteria**:
- Test coverage > 80%
- All examples run successfully
- Documentation clear and complete
- Configuration templates provided

**Commit**: Single commit with tests and docs

## Risk Mitigation Strategies

### Technical Risks
1. **SearchVectara Compatibility**
   - Mitigation: Early prototype of BaseRagTool in Phase 1
   - Fallback: Create shim layer if interface mismatch

2. **Claude 4.1 Opus API Access**
   - Mitigation: Test API access before Phase 3
   - Fallback: Use Claude 3.5 Sonnet if 4.1 unavailable

3. **Goodmem API Unknown Structure**
   - Mitigation: Flexible normalizer with logging
   - Fallback: Raw response display if normalization fails

### Process Risks
1. **Phase Dependencies**
   - Mitigation: Each phase independently testable
   - Fallback: Mock implementations for testing

2. **Time Constraints**
   - Mitigation: Core features in early phases
   - Fallback: Defer HTML export or batch processing

## Development Guidelines

### Code Standards
- Type hints for all function signatures
- Docstrings for public methods
- Error messages include context and suggestions
- Logging at appropriate levels (DEBUG, INFO, ERROR)

### Testing Approach
- Unit tests alongside implementation
- Integration tests at phase boundaries
- Manual testing with real queries
- Performance benchmarking for latency claims

### Documentation Requirements
- Inline comments for complex logic
- README with quickstart guide
- Configuration documentation
- Example outputs for reference

## Completion Checklist
- [ ] All phases committed to git
- [ ] Tests passing with good coverage
- [ ] Documentation complete
- [ ] Example queries demonstrate value
- [ ] Performance meets specifications
- [ ] Error handling comprehensive
- [ ] Configuration secure (no hardcoded secrets)

## Notes
- No time estimates per SPIDER protocol guidelines
- Each phase represents a complete, testable unit
- Commits mark phase boundaries for clear progress
- Focus on subjective evaluation over metrics
- Prioritize user experience in display design
