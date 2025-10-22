# RAGDiff Development Documentation (codev)

This directory contains all development documentation for the RAGDiff project following the SPIDER protocol.

## Directory Structure

```
codev/
├── specs/          # Specifications (what to build)
├── plans/          # Implementation plans (how to build)
├── reviews/        # Code reviews (quality assessment)
├── protocols/      # SPIDER protocol templates
└── resources/      # Reference materials
```

## Current Documentation

### 0001: RAG Comparison Harness
**Status**: ✅ Completed

Initial implementation of the RAG comparison tool with Vectara and Goodmem adapters.

- **Spec**: [specs/0001-rag-comparison-harness.md](specs/0001-rag-comparison-harness.md)
- **Plan**: [plans/0001-rag-comparison-harness.md](plans/0001-rag-comparison-harness.md)
- **Review**: [reviews/0001-rag-comparison-harness.md](reviews/0001-rag-comparison-harness.md)

### 0002: Adapter Variants Support
**Status**: ✅ Completed

Enable flexible adapter variants through YAML configuration, allowing comparison of different configurations of the same RAG tool.

- **Spec**: [specs/0002-adapter-variants.md](specs/0002-adapter-variants.md)
- **Plan**: [plans/0002-adapter-variants.md](plans/0002-adapter-variants.md)
- **Review**: [reviews/0002-adapter-variants.md](reviews/0002-adapter-variants.md)

**Key Features**:
- Multiple variants of same adapter via YAML
- Custom options per variant
- Backward compatible with existing configs
- No code changes needed to add variants

### 0003: Library Refactoring
**Status**: ✅ Completed (v1.0.0)

Transform RAGDiff from CLI-only tool to dual-interface library with stable public API.

- **Spec**: [specs/0003-library-refactoring.md](specs/0003-library-refactoring.md)
- **Plan**: [plans/0003-library-refactoring.md](plans/0003-library-refactoring.md)
- **Review**: [reviews/0003-library-refactoring-final-review.md](reviews/0003-library-refactoring-final-review.md)

**Key Features**:
- Public Python API with 6 core functions
- Thread-safe concurrent execution
- Comprehensive error handling
- FastAPI integration support
- Production-ready v1.0.0 release

## SPIDER Protocol

RAGDiff follows the SPIDER protocol for all development:

- **S**pecification - What to build and why
- **P**lan - How to build it step-by-step
- **I**mplement - Write the code
- **D**ocument - Update docs and examples
- **E**valuate - Test and verify
- **R**eview - Quality assessment and approval

See [protocols/spider/](protocols/spider/) for templates and guidelines.

## Resources

- **[arch.md](resources/arch.md)** - System architecture overview
- **[goodmem-operational.md](resources/goodmem-operational.md)** - Goodmem adapter operational guide

## Changelog

All notable changes are documented in [CHANGELOG.md](../CHANGELOG.md) in the project root.

## Version History

- **v1.0.0** (2025-10-21) - Production release with library API
- **v0.9.0** (2025-01-15) - CLI implementation
- **v0.1.0** (2024-12-01) - Initial project structure
