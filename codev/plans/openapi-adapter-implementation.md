# Implementation Plan: OpenAPI Adapter System

**Based on Spec**: `codev/specs/openapi-adapter-system.md`
**Created**: 2025-10-25
**Status**: Planning

---

## Overview

This plan implements the OpenAPI Adapter System in 5 phases, building from foundation to polish. Each phase is independently testable and provides incremental value.

**Total Estimated Effort**: 3-4 weeks (assuming focused development)

---

## Phase 1: Core OpenAPI Adapter (Foundation)

**Goal**: Create the runtime adapter that works with manually-written configs

**Duration**: 5-7 days

### Tasks

#### 1.1 Create Response Mapping Engine

**File**: `src/ragdiff/adapters/openapi_mapping.py`

**Subtasks**:
- [ ] Install `jmespath` dependency (update `pyproject.toml`)
- [ ] Create `TemplateEngine` class for `${var}` substitution
  - [ ] Support string templates: `"${query}"`
  - [ ] Support numeric templates: `${top_k}`
  - [ ] Support nested dicts
  - [ ] Handle escaping if needed
- [ ] Create `ResponseMapper` class
  - [ ] Initialize with mapping config dict
  - [ ] `map_results(response: dict) -> list[RagResult]`
  - [ ] `_extract_field(item, jmespath_expr)` using jmespath library
  - [ ] `_normalize_score(score)` (reuse existing logic)
  - [ ] Handle missing fields gracefully (log warnings, use defaults)
- [ ] Write comprehensive unit tests
  - [ ] Test various JMESPath patterns (simple paths, array access, object construction)
  - [ ] Test score normalization (0-1, 0-100, 0-1000)
  - [ ] Test missing fields with defaults
  - [ ] Test malformed JMESPath (should raise ConfigurationError)

**Acceptance Criteria**:
- [ ] JMESPath extracts fields correctly from test dicts
- [ ] Template substitution works for all variable types
- [ ] Score normalization handles all ranges
- [ ] 100% test coverage on mapping module

#### 1.2 Create OpenAPIAdapter Class

**File**: `src/ragdiff/adapters/openapi.py`

**Subtasks**:
- [ ] Create `OpenAPIAdapter(RagAdapter)` class
  - [ ] Set `ADAPTER_NAME = "openapi"`
  - [ ] Set `ADAPTER_API_VERSION = "1.0.0"`
- [ ] Implement `__init__(config, credentials)`
  - [ ] Extract `options` dict from config
  - [ ] Validate required fields (base_url, endpoint, auth, response_mapping)
  - [ ] Get API credentials via `_get_credential()`
  - [ ] Initialize ResponseMapper with mapping config
  - [ ] Store configuration
- [ ] Implement `validate_config(config)`
  - [ ] Check required fields present
  - [ ] Validate auth configuration
  - [ ] Validate response_mapping structure
  - [ ] Test JMESPath expressions are valid syntax
- [ ] Implement `search(query, top_k) -> list[RagResult]`
  - [ ] Build request with `_build_request()`
  - [ ] Execute request with `_execute_request()`
  - [ ] Map response with ResponseMapper
  - [ ] Sort by score descending
  - [ ] Return top_k results
- [ ] Implement `_build_request(query, top_k) -> dict`
  - [ ] Apply template substitution to request_body
  - [ ] Apply template substitution to request_params
  - [ ] Build headers with authentication
  - [ ] Return dict with {method, url, headers, json, params}
- [ ] Implement `_execute_request(request_dict) -> dict`
  - [ ] Use `requests` library
  - [ ] Handle timeouts (from config.timeout)
  - [ ] Exponential backoff retry (up to config.max_retries)
  - [ ] Parse JSON response
  - [ ] Raise AdapterError on failures with clear messages
- [ ] Implement authentication support
  - [ ] Bearer token: `Authorization: Bearer {token}`
  - [ ] API Key header: `{header_name}: {key}`
  - [ ] API Key query param: append to URL params
  - [ ] Basic auth: `requests.auth.HTTPBasicAuth`

**Acceptance Criteria**:
- [ ] Adapter implements full RagAdapter interface
- [ ] Can make authenticated requests to APIs
- [ ] Maps responses to RagResult correctly
- [ ] Error handling is comprehensive and clear
- [ ] All auth types work

#### 1.3 Register OpenAPI Adapter

**Files**: `src/ragdiff/adapters/__init__.py`, `src/ragdiff/adapters/openapi.py`

**Subtasks**:
- [ ] Add registration call at bottom of `openapi.py`:
  ```python
  from .registry import register_adapter
  register_adapter(OpenAPIAdapter)
  ```
- [ ] Import in `__init__.py`:
  ```python
  from . import openapi  # noqa: F401
  ```
- [ ] Verify registration works with unit test

**Acceptance Criteria**:
- [ ] `list_available_adapters()` includes "openapi"
- [ ] Can create adapter via factory: `create_adapter("openapi", config)`

#### 1.4 Write Tests for OpenAPIAdapter

**File**: `tests/test_openapi_adapter.py`

**Subtasks**:
- [ ] Create mock API server fixture (using `responses` library or Flask)
- [ ] Test request building
  - [ ] Test template substitution in body
  - [ ] Test template substitution in params
  - [ ] Test all auth types
- [ ] Test response mapping
  - [ ] Test with simple response structure
  - [ ] Test with nested structure
  - [ ] Test with arrays
  - [ ] Test with missing fields (should handle gracefully)
- [ ] Test error handling
  - [ ] Network errors (connection refused, timeout)
  - [ ] HTTP errors (401, 404, 500)
  - [ ] Invalid JSON responses
  - [ ] Missing required fields in response
- [ ] Test end-to-end with mock API
  - [ ] Create config dict
  - [ ] Initialize adapter
  - [ ] Execute search
  - [ ] Verify RagResults

**Acceptance Criteria**:
- [ ] 90%+ test coverage on openapi.py
- [ ] All error paths tested
- [ ] Tests use realistic mock data

#### 1.5 Create Example Manual Config

**File**: `configs/examples/openapi-example.yaml`

**Subtasks**:
- [ ] Create example config with comments
- [ ] Document all fields
- [ ] Provide simple and complex examples
- [ ] Add to git

**Example**:
```yaml
# Example OpenAPI adapter configuration
# This is a manually written config for reference

example-api:
  adapter: openapi
  api_key_env: EXAMPLE_API_KEY
  timeout: 30
  max_retries: 3

  options:
    # API endpoint configuration
    base_url: https://api.example.com
    endpoint: /v1/search
    method: POST  # GET, POST, PUT, etc.

    # Authentication (Bearer token example)
    auth:
      type: bearer  # bearer, api_key, basic
      header: Authorization
      scheme: Bearer

    # Request template (${query} and ${top_k} are substituted)
    request_body:
      query: "${query}"
      limit: ${top_k}
      filters:
        language: "ar"

    # Response mapping (JMESPath expressions)
    response_mapping:
      # Path to array of results
      results_array: "data.results"

      # Field mappings (JMESPath from each result item)
      fields:
        id: "id"
        text: "content.text"
        score: "relevance_score"
        source: "source.name"
        metadata: "{author: metadata.author, date: published_date}"
```

**Acceptance Criteria**:
- [ ] Example config is well-documented
- [ ] Can be used as template for manual configs

#### 1.6 Manual Integration Test

**Task**: Test adapter with a real API (if available) or comprehensive mock

**Subtasks**:
- [ ] Create manual test config
- [ ] Test with mock API server
- [ ] Verify all functionality works
- [ ] Document any issues found

**Acceptance Criteria**:
- [ ] Adapter works end-to-end with manually written config
- [ ] Results are valid RagResult objects

### Phase 1 Deliverables

- [x] Working OpenAPIAdapter class
- [x] Response mapping with JMESPath
- [x] All authentication types supported
- [x] Comprehensive tests (90%+ coverage)
- [x] Example config documented
- [x] All existing RAGDiff tests still pass

---

## Phase 2: OpenAPI Spec Parser

**Goal**: Parse OpenAPI specifications to extract endpoint and auth metadata

**Duration**: 3-4 days

### Tasks

#### 2.1 Create OpenAPI Parser Module

**File**: `src/ragdiff/openapi/__init__.py`

**Subtasks**:
- [ ] Create `openapi/` package directory
- [ ] Add `__init__.py` with exports

#### 2.2 Implement OpenAPI Spec Models

**File**: `src/ragdiff/openapi/models.py`

**Subtasks**:
- [ ] Create `EndpointInfo` dataclass
  ```python
  @dataclass
  class EndpointInfo:
      path: str
      method: str
      summary: str
      description: str
      operation_id: Optional[str]
      parameters: list[dict]
      request_body_schema: Optional[dict]
      response_schema: Optional[dict]
  ```
- [ ] Create `AuthScheme` dataclass
  ```python
  @dataclass
  class AuthScheme:
      type: str  # apiKey, http, oauth2
      name: str
      scheme: Optional[str]  # bearer, basic
      location: Optional[str]  # header, query, cookie
  ```
- [ ] Create `OpenAPIInfo` dataclass for spec metadata

**Acceptance Criteria**:
- [ ] Models are well-typed with Pydantic or dataclasses
- [ ] All relevant OpenAPI fields captured

#### 2.3 Implement OpenAPI Spec Parser

**File**: `src/ragdiff/openapi/parser.py`

**Subtasks**:
- [ ] Create `OpenAPISpec` class
  ```python
  class OpenAPISpec:
      def __init__(self, spec_dict: dict):
          """Initialize from parsed JSON/YAML dict."""
          pass

      @classmethod
      def from_url(cls, url: str) -> "OpenAPISpec":
          """Fetch spec from URL and parse."""
          pass

      @classmethod
      def from_file(cls, path: str) -> "OpenAPISpec":
          """Load spec from local file."""
          pass

      def get_endpoints(self) -> list[EndpointInfo]:
          """Extract all endpoints from spec."""
          pass

      def get_auth_schemes(self) -> list[AuthScheme]:
          """Extract authentication schemes."""
          pass

      def get_endpoint(self, path: str, method: str) -> Optional[EndpointInfo]:
          """Get specific endpoint details."""
          pass
  ```
- [ ] Implement `from_url()`
  - [ ] Use `requests.get()` to fetch spec
  - [ ] Handle redirects
  - [ ] Detect JSON vs YAML (try JSON first, fall back to YAML)
  - [ ] Handle common spec locations:
    - `/openapi.json`
    - `/openapi.yaml`
    - `/swagger.json`
    - User-provided URL
- [ ] Implement `from_file()`
  - [ ] Read file
  - [ ] Detect format (JSON/YAML)
  - [ ] Parse with appropriate library
- [ ] Implement `get_endpoints()`
  - [ ] Walk `paths` dict
  - [ ] For each path, extract methods (get, post, etc.)
  - [ ] Parse parameters, requestBody, responses
  - [ ] Create EndpointInfo objects
- [ ] Implement `get_auth_schemes()`
  - [ ] Parse `components.securitySchemes`
  - [ ] Create AuthScheme objects
  - [ ] Handle multiple schemes

**Acceptance Criteria**:
- [ ] Can fetch specs from URLs
- [ ] Can parse OpenAPI 3.0 and 3.1 specs
- [ ] Extracts endpoints correctly
- [ ] Extracts auth schemes correctly
- [ ] Handles JSON and YAML formats

#### 2.4 Write Parser Tests

**File**: `tests/test_openapi_parser.py`

**Subtasks**:
- [ ] Create test fixtures
  - [ ] Sample OpenAPI 3.0 spec (JSON)
  - [ ] Sample OpenAPI 3.1 spec (YAML)
  - [ ] Real-world example (Swagger Petstore)
- [ ] Test `from_url()`
  - [ ] Mock HTTP responses
  - [ ] Test JSON and YAML specs
  - [ ] Test 404 errors
  - [ ] Test invalid JSON/YAML
- [ ] Test `from_file()`
  - [ ] Test with JSON file
  - [ ] Test with YAML file
  - [ ] Test with missing file
- [ ] Test `get_endpoints()`
  - [ ] Verify all endpoints extracted
  - [ ] Verify parameters parsed correctly
  - [ ] Verify request/response schemas captured
- [ ] Test `get_auth_schemes()`
  - [ ] Test Bearer auth detection
  - [ ] Test API Key auth detection
  - [ ] Test Basic auth detection

**Acceptance Criteria**:
- [ ] 90%+ test coverage on parser
- [ ] Tests use real OpenAPI spec examples
- [ ] Error cases handled

#### 2.5 Integration Test with Real Specs

**Subtasks**:
- [ ] Test with Swagger Petstore spec
  - URL: https://petstore3.swagger.io/api/v3/openapi.json
- [ ] Test with Kalimat spec (if available)
- [ ] Verify extraction is correct

**Acceptance Criteria**:
- [ ] Can parse real-world specs successfully
- [ ] Extracted data is accurate

### Phase 2 Deliverables

- [x] OpenAPI spec parser
- [x] Can fetch and parse specs from URLs
- [x] Extracts endpoints and auth metadata
- [x] Comprehensive tests
- [x] Works with real OpenAPI specs

---

## Phase 3: AI Configuration Generator

**Goal**: CLI command that generates adapter configs automatically using AI

**Duration**: 7-10 days

### Tasks

#### 3.1 Add Anthropic Dependency

**File**: `pyproject.toml`

**Subtasks**:
- [ ] Add `anthropic` to dependencies
- [ ] Run `uv pip install anthropic`
- [ ] Add `ANTHROPIC_API_KEY` to environment setup

**Acceptance Criteria**:
- [ ] Can import `anthropic` library
- [ ] API key available in environment

#### 3.2 Create AI Analysis Module

**File**: `src/ragdiff/openapi/ai_analyzer.py`

**Subtasks**:
- [ ] Create `AIAnalyzer` class
  ```python
  class AIAnalyzer:
      def __init__(self, api_key: str):
          self.client = anthropic.Anthropic(api_key=api_key)

      async def identify_search_endpoint(
          self, endpoints: list[EndpointInfo]
      ) -> tuple[str, str]:
          """Returns (path, method) of likely search endpoint."""
          pass

      async def generate_response_mapping(
          self, example_response: dict
      ) -> dict:
          """Generate JMESPath mappings from example response."""
          pass
  ```
- [ ] Implement `identify_search_endpoint()`
  - [ ] Build prompt with endpoint list
  - [ ] Call Claude API
  - [ ] Parse response (expect JSON with {path, method, reasoning})
  - [ ] Validate response
- [ ] Implement `generate_response_mapping()`
  - [ ] Build prompt with response JSON and required fields
  - [ ] Call Claude API
  - [ ] Parse mapping configuration
  - [ ] Validate JMESPath expressions
- [ ] Add error handling
  - [ ] API errors (rate limits, auth)
  - [ ] Invalid responses (malformed JSON)
  - [ ] Timeout handling

**Prompts to implement**:

**Prompt 1: Endpoint Identification**
```python
ENDPOINT_IDENTIFICATION_PROMPT = """
You are analyzing an OpenAPI specification to identify the search/query endpoint
for a RAG (Retrieval-Augmented Generation) system.

Available endpoints:
{endpoint_list}

Identify which endpoint is most likely used for searching or querying documents.
Look for endpoints with names like: search, query, find, retrieve, etc.

Respond with JSON in this exact format:
{
  "path": "/v1/search",
  "method": "POST",
  "reasoning": "This endpoint has 'search' in the name and accepts a query parameter"
}
"""
```

**Prompt 2: Response Mapping**
```python
RESPONSE_MAPPING_PROMPT = """
You are analyzing an API response to generate JMESPath expressions for extracting
search result fields.

Required fields to extract:
- id: Unique identifier (string)
- text: Main content text (string)
- score: Relevance score (float, ideally 0-1 range)
- source: Source document/name (string, optional)
- metadata: Additional metadata (dict, optional)

Example API response:
{response_json}

Generate JMESPath expressions to extract these fields. For the results_array,
provide the path to the array of result items.

Respond with JSON in this exact format:
{
  "results_array": "data.results",
  "fields": {
    "id": "id",
    "text": "content.text",
    "score": "relevance_score",
    "source": "source.name",
    "metadata": "{{author: metadata.author, date: published_date}}"
  }
}

Note: For metadata, construct a JMESPath object expression using {{key: path}} syntax.
"""
```

**Acceptance Criteria**:
- [ ] Can call Claude API successfully
- [ ] Parses structured responses
- [ ] Handles API errors gracefully

#### 3.3 Create Configuration Generator

**File**: `src/ragdiff/openapi/generator.py`

**Subtasks**:
- [ ] Create `ConfigGenerator` class
  ```python
  class ConfigGenerator:
      def __init__(self, anthropic_api_key: str):
          self.ai_analyzer = AIAnalyzer(anthropic_api_key)

      async def generate(
          self,
          openapi_url: str,
          api_key: str,
          test_query: str,
          adapter_name: str,
          endpoint: Optional[str] = None,
          method: Optional[str] = None,
      ) -> dict:
          """Generate complete adapter configuration."""
          pass
  ```
- [ ] Implement `generate()` workflow:
  1. Fetch OpenAPI spec
  2. If endpoint not provided, use AI to identify it
  3. Extract auth scheme from spec
  4. Make test query to API
  5. Use AI to generate response mapping
  6. Construct full config dict
  7. Validate config by creating adapter and querying
  8. Return config dict
- [ ] Implement validation step
  - [ ] Create `OpenAPIAdapter` with generated config
  - [ ] Execute test query
  - [ ] Verify results are valid
  - [ ] Raise error if validation fails

**Acceptance Criteria**:
- [ ] End-to-end generation works
- [ ] Validates generated config
- [ ] Returns complete, usable config

#### 3.4 Add CLI Command

**File**: `src/ragdiff/cli.py`

**Subtasks**:
- [ ] Add `generate-adapter` command to Typer app
  ```python
  @app.command()
  def generate_adapter(
      openapi_url: str = typer.Option(..., help="OpenAPI spec URL"),
      api_key: str = typer.Option(..., help="API key for authentication"),
      test_query: str = typer.Option(..., help="Test query string"),
      adapter_name: str = typer.Option(..., help="Name for the adapter"),
      output: Optional[str] = typer.Option(None, help="Output file path"),
      endpoint: Optional[str] = typer.Option(None, help="Override endpoint path"),
      method: Optional[str] = typer.Option(None, help="Override HTTP method"),
      interactive: bool = typer.Option(False, help="Interactive confirmation mode"),
  ):
      """Generate OpenAPI adapter configuration from spec."""
      pass
  ```
- [ ] Implement command logic:
  1. Get Anthropic API key from environment
  2. Call ConfigGenerator.generate()
  3. If interactive, show generated config and ask for confirmation
  4. Convert config dict to YAML
  5. Add helpful comments to YAML
  6. Write to output file or stdout
  7. Show success message with usage example
- [ ] Add interactive mode
  - [ ] Show identified endpoint, ask to confirm
  - [ ] Show generated mapping, ask to confirm
  - [ ] Show test results
  - [ ] Allow manual override

**Acceptance Criteria**:
- [ ] CLI command works end-to-end
- [ ] Outputs valid YAML
- [ ] Interactive mode provides good UX
- [ ] Error messages are helpful

#### 3.5 Add YAML Output Formatting

**File**: `src/ragdiff/openapi/yaml_formatter.py`

**Subtasks**:
- [ ] Create function to format config as YAML with comments
  ```python
  def format_config_yaml(config: dict, metadata: dict) -> str:
      """Format config as YAML with helpful comments."""
      pass
  ```
- [ ] Add metadata comments:
  - Generated timestamp
  - OpenAPI spec URL
  - Test query used
  - Usage instructions
- [ ] Format nicely with indentation

**Example output**:
```yaml
# Generated by: ragdiff generate-adapter
# OpenAPI Spec: https://api.kalimat.dev/openapi.json
# Test Query: "what is tawhid"
# Generated: 2025-10-25T10:30:00Z
#
# Usage:
#   uv run ragdiff query "your query" --tool kalimat --config path/to/this/file.yaml

kalimat:
  adapter: openapi
  api_key_env: KALIMAT_API_KEY
  # ... rest of config
```

**Acceptance Criteria**:
- [ ] YAML is well-formatted and readable
- [ ] Comments are helpful
- [ ] Can be used immediately

#### 3.6 Write Generator Tests

**File**: `tests/test_adapter_generator.py`

**Subtasks**:
- [ ] Mock OpenAPI spec responses
- [ ] Mock Claude API responses
- [ ] Mock test API responses
- [ ] Test successful generation
  - [ ] Verify config structure
  - [ ] Verify validation passes
- [ ] Test error cases
  - [ ] Invalid OpenAPI spec URL
  - [ ] Failed test query
  - [ ] AI returns invalid mapping
  - [ ] Validation fails
- [ ] Integration test (if possible with real API)

**Acceptance Criteria**:
- [ ] 80%+ test coverage on generator
- [ ] All error paths tested
- [ ] Mocks are realistic

### Phase 3 Deliverables

- [x] `ragdiff generate-adapter` command works
- [x] AI identifies endpoints and generates mappings
- [x] Generated configs are validated
- [x] YAML output is well-formatted
- [x] Comprehensive tests
- [x] Error handling is robust

---

## Phase 4: Real-World Validation

**Goal**: Validate system with actual APIs and iterate based on findings

**Duration**: 5-7 days

### Tasks

#### 4.1 Generate Config for Kalimat API

**Subtasks**:
- [ ] Get Kalimat API key (if available)
- [ ] Identify OpenAPI spec URL
- [ ] Run `generate-adapter` command
- [ ] Review generated config
- [ ] Test with real queries
- [ ] Document any issues or manual adjustments needed

**Acceptance Criteria**:
- [ ] Generated config works for Kalimat API
- [ ] Results are accurate
- [ ] No code changes needed

#### 4.2 Generate Config for Second API

**Subtasks**:
- [ ] Identify another RAG API with OpenAPI spec
  - Options: Elasticsearch, Algolia, Typesense, Meilisearch
- [ ] Run generator
- [ ] Test thoroughly
- [ ] Compare results with manual integration

**Acceptance Criteria**:
- [ ] Second API also works
- [ ] System handles different response structures

#### 4.3 Identify and Fix Edge Cases

**Subtasks**:
- [ ] Document edge cases discovered
- [ ] Fix bugs found during real-world testing
- [ ] Update error messages based on real failures
- [ ] Improve AI prompts if mappings are wrong

**Acceptance Criteria**:
- [ ] All discovered bugs fixed
- [ ] Edge cases documented

#### 4.4 Add Example Configs to Repo

**Files**: `configs/kalimat.yaml`, `configs/second-api.yaml`

**Subtasks**:
- [ ] Save generated configs as examples
- [ ] Add comments explaining customizations
- [ ] Add to git

**Acceptance Criteria**:
- [ ] Example configs are in repo
- [ ] Can be used as reference

#### 4.5 Performance Testing

**Subtasks**:
- [ ] Measure generation time (should be < 60s)
- [ ] Measure query overhead (should be < 100ms)
- [ ] Measure mapping overhead (should be < 10ms per result)
- [ ] Optimize if needed

**Acceptance Criteria**:
- [ ] Performance metrics met
- [ ] No obvious bottlenecks

### Phase 4 Deliverables

- [x] Validated with 2+ real APIs
- [x] Edge cases identified and fixed
- [x] Example configs in repo
- [x] Performance acceptable
- [x] Known limitations documented

---

## Phase 5: Documentation & Polish

**Goal**: Production-ready with comprehensive documentation

**Duration**: 3-5 days

### Tasks

#### 5.1 Update Architecture Documentation

**File**: `codev/resources/arch.md`

**Subtasks**:
- [ ] Document OpenAPI adapter system
- [ ] Describe new modules (openapi/, generator, etc.)
- [ ] Update component diagram
- [ ] Add decision records (JMESPath choice, etc.)

**Acceptance Criteria**:
- [ ] Arch doc reflects new system
- [ ] All components documented

#### 5.2 Create User Guide

**File**: `docs/openapi-adapter-guide.md` (new)

**Subtasks**:
- [ ] Write guide covering:
  - [ ] What the OpenAPI adapter system is
  - [ ] How to use `generate-adapter` command
  - [ ] How to customize generated configs
  - [ ] JMESPath primer
  - [ ] Authentication options
  - [ ] Troubleshooting common issues
  - [ ] Known limitations
- [ ] Add examples with screenshots/output

**Acceptance Criteria**:
- [ ] User can follow guide to generate their first adapter
- [ ] Common questions answered

#### 5.3 Update README

**File**: `README.md`

**Subtasks**:
- [ ] Add section on OpenAPI adapter system
- [ ] Add `generate-adapter` to command list
- [ ] Add example of usage
- [ ] Update feature list

**Acceptance Criteria**:
- [ ] README mentions OpenAPI system
- [ ] Users know it exists and how to use it

#### 5.4 Update CLAUDE.md

**File**: `CLAUDE.md`

**Subtasks**:
- [ ] Document new modules
- [ ] Update project structure
- [ ] Add notes on OpenAPI adapter development
- [ ] Add JMESPath info

**Acceptance Criteria**:
- [ ] Claude Code instructions updated
- [ ] Future development easier

#### 5.5 Add Docstrings

**All Files**

**Subtasks**:
- [ ] Ensure all classes have docstrings
- [ ] Ensure all public methods have docstrings
- [ ] Add type hints everywhere
- [ ] Run mypy to verify

**Acceptance Criteria**:
- [ ] Full docstring coverage
- [ ] mypy passes with no errors

#### 5.6 Update CLI Help

**File**: `src/ragdiff/cli.py`

**Subtasks**:
- [ ] Improve help text for `generate-adapter`
- [ ] Add examples to --help output
- [ ] Ensure all options documented

**Acceptance Criteria**:
- [ ] `ragdiff generate-adapter --help` is comprehensive

#### 5.7 Create Troubleshooting Guide

**File**: `docs/troubleshooting-openapi.md` (new)

**Subtasks**:
- [ ] Document common errors:
  - "Cannot identify search endpoint" → use --endpoint
  - "JMESPath extraction failed" → check response structure
  - "Authentication failed" → verify API key
  - etc.
- [ ] Add solutions for each

**Acceptance Criteria**:
- [ ] Common issues have solutions

#### 5.8 Version Bump and Changelog

**Files**: `src/ragdiff/version.py`, `CHANGELOG.md`

**Subtasks**:
- [ ] Bump version to 1.2.0 (new features, backward compatible)
- [ ] Update CHANGELOG with all changes:
  - New OpenAPI adapter system
  - New generate-adapter command
  - JMESPath response mapping
  - AI-assisted config generation
- [ ] Update version in tests if needed

**Acceptance Criteria**:
- [ ] Version is 1.2.0
- [ ] CHANGELOG is complete

### Phase 5 Deliverables

- [x] Complete documentation (arch, user guide, README)
- [x] Full docstring coverage
- [x] Troubleshooting guide
- [x] Version bumped to 1.2.0
- [x] CHANGELOG updated
- [x] Production-ready

---

## Testing Strategy Summary

### Test Coverage Goals

- **Unit Tests**: 90%+ coverage for all new modules
- **Integration Tests**: Cover full generator workflow
- **Real-World Tests**: At least 2 real APIs working

### Test Files

- `tests/test_openapi_mapping.py`: Response mapping and templates
- `tests/test_openapi_adapter.py`: OpenAPI adapter runtime
- `tests/test_openapi_parser.py`: OpenAPI spec parsing
- `tests/test_adapter_generator.py`: AI generation workflow
- `tests/test_openapi_integration.py`: End-to-end tests

### Continuous Testing

- All existing RAGDiff tests must pass
- Pre-commit hooks must pass
- New tests run in CI

---

## Dependencies

### New Dependencies to Add

```toml
[project.dependencies]
jmespath = "^1.0.1"  # JMESPath for response mapping
anthropic = "^0.40.0"  # Claude API for generation
```

### Existing Dependencies to Leverage

- `requests`: HTTP requests
- `pydantic`: Configuration validation
- `pyyaml`: YAML parsing
- `typer`: CLI framework
- `pytest`: Testing
- `ruff`: Linting

---

## Risk Management

### Risk: AI-Generated Mappings Incorrect

**Mitigation**:
- Always validate with test query before saving
- Interactive mode for confirmation
- Save failed examples for improvement
- Document manual override process

### Risk: OpenAPI Specs Vary

**Mitigation**:
- Start with well-formed specs
- Graceful degradation
- Document known limitations
- Allow manual config editing

### Risk: Timeline Slippage

**Mitigation**:
- Each phase is independently valuable
- Can release after Phase 3 if needed
- Phases 4-5 are polish, not critical

---

## Success Criteria (Final)

### Functional

- [ ] Generator creates working config for 2+ real APIs
- [ ] Generated configs work without manual editing (90%+ success)
- [ ] All existing RAGDiff tests pass
- [ ] New tests achieve 90%+ coverage

### Performance

- [ ] Config generation < 60 seconds
- [ ] Query overhead < 100ms
- [ ] Mapping overhead < 10ms per result

### Quality

- [ ] All pre-commit hooks pass
- [ ] Full type hints (mypy clean)
- [ ] Complete documentation
- [ ] Arch doc updated

### Usability

- [ ] Intuitive CLI (can use without reading docs)
- [ ] Clear error messages
- [ ] Generated YAML is readable

---

## Rollout Plan

### Development Branch

- Create branch: `feature/openapi-adapter-system`
- Develop all phases on this branch
- Merge to main when Phase 5 complete

### Incremental Merges (Optional)

- Could merge after Phase 1 (foundation)
- Could merge after Phase 3 (generator)
- Or merge all at once after Phase 5

### Release

- Tag version 1.2.0 when complete
- Update documentation
- Announce new feature

---

## Timeline Summary

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 5-7 days | Core adapter with manual configs |
| Phase 2 | 3-4 days | OpenAPI spec parser |
| Phase 3 | 7-10 days | AI configuration generator |
| Phase 4 | 5-7 days | Real-world validation |
| Phase 5 | 3-5 days | Documentation & polish |
| **Total** | **23-33 days** | **Production-ready system** |

**Estimated Calendar Time**: 3-4 weeks with focused development

---

## Next Steps

1. **Review this plan** and adjust as needed
2. **Get approval** to proceed
3. **Create feature branch**: `feature/openapi-adapter-system`
4. **Begin Phase 1, Task 1.1**: Install jmespath and create ResponseMapper

---

**End of Implementation Plan**
