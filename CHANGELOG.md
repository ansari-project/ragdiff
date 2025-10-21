# Changelog

All notable changes to RAGDiff will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-21

### Added

**Library API (Phase 1-4)**
- Public Python API with 6 core functions: `query()`, `compare()`, `run_batch()`, `evaluate_with_llm()`, `load_config()`, `validate_config()`, `get_available_adapters()`
- Top-level imports from `ragdiff` package for easy access
- Comprehensive API documentation with examples
- Full type hints for all public interfaces
- Structured error handling with custom exception hierarchy

**Thread-Safety & Stability (Phase 5)**
- Thread-safe adapter registry with `threading.RLock()` for concurrent access
- Centralized serialization module (`ragdiff.core.serialization`) with thread-safe JSON conversion
- Zero global mutable state across the library
- Support for concurrent execution in web servers and multi-threaded applications
- 27 comprehensive serialization tests

**Testing & Quality (Phase 5-6)**
- Parity test framework for CLI/library consistency validation
- Normalization utilities for comparing outputs across interfaces
- 7 parity framework tests (all passing)
- Thread-safety test infrastructure
- Reentrancy test infrastructure

**Documentation & Examples (Phase 7)**
- Complete library API documentation in README
- FastAPI integration example (`examples/fastapi_integration.py`)
- Thread-safe usage examples
- Error handling examples
- Configuration management examples

**Code Quality**
- Module-level constants for better performance (`_SPACE_NAMES` in goodmem adapter)
- Comprehensive docstrings for all public functions
- Type hints coverage: 100% for public interface
- Linting: 0 errors/warnings

### Changed

**Architecture**
- Refactored from CLI-only tool to dual-interface library
- Adapters now implement standardized `RagAdapter` ABC
- Centralized adapter registry with version compatibility checking
- Consistent error handling across all interfaces

**Performance**
- Reduced memory allocation by extracting hardcoded dictionaries
- Thread-safe concurrent execution support
- Parallel query execution in batch mode

### Fixed
- Thread-safety issues in global adapter registry
- Potential race conditions in class variables
- Inefficient repeated dictionary creation in adapters

### Removed
- Deprecated direct adapter imports (use registry instead)

## [0.9.0] - 2025-01-15

### Added
- Initial CLI implementation
- Support for Vectara, Goodmem, and Agentset adapters
- LLM evaluation using Claude
- Multiple output formats (JSON, Markdown, summary)
- Batch processing with holistic summaries

### Changed
- Migrated from pip to uv for dependency management
- Updated to use Typer for CLI implementation

## [0.1.0] - 2024-12-01

### Added
- Initial project structure
- Basic comparison engine
- Vectara adapter

[1.0.0]: https://github.com/ansari-project/ragdiff/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/ansari-project/ragdiff/compare/v0.1.0...v0.9.0
[0.1.0]: https://github.com/ansari-project/ragdiff/releases/tag/v0.1.0
