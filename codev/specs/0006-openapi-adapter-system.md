# SPIDER Specification: OpenAPI Adapter System

**Status**: Draft
**Created**: 2025-10-25
**Version**: 1.0

## 1. Specification (Goals & Requirements)

### 1.1 Vision

Build a meta-adapter system that can automatically generate RAGDiff adapters from arbitrary OpenAPI specifications, enabling zero-code integration of new RAG systems.

### 1.2 Core User Stories

**As a RAGDiff user**, I want to:
1. Generate a working adapter config from an OpenAPI spec URL in < 60 seconds
2. Use the generated adapter immediately without writing code
3. Query any OpenAPI-compliant search API using the same RAGDiff interface
4. Customize mappings if the AI-generated config needs tweaking

**As a RAGDiff developer**, I want to:
1. Support new RAG systems without writing adapter code
2. Maintain consistent error handling and normalization
3. Leverage existing configuration and multi-tenant systems
4. Add new APIs by just adding YAML configs

### 1.3 Success Criteria

1. **Generator CLI works end-to-end**:
   - Fetches OpenAPI spec from URL
   - Identifies search endpoint with AI assistance
   - Makes test query with provided credentials
   - Generates valid YAML config
   - Validates config by executing test query

2. **Generic adapter handles diverse APIs**:
   - Works with REST APIs (JSON request/response)
   - Supports common auth: API Key, Bearer token, Basic auth
   - Maps arbitrary response structures to RagResult
   - Handles pagination (at least simple limit/offset)

3. **Zero code for new integrations**:
   - Example: Kalimat API adapter created purely from config
   - Example: Second API with different structure also works
   - No Python code required after initial implementation

4. **Maintains RAGDiff quality standards**:
   - All tests pass (existing + new)
   - Pre-commit hooks pass
   - Full type hints
   - Comprehensive error messages

### 1.4 Non-Goals (Out of Scope)

1. **Complex Authentication**: OAuth flows, JWT refresh (v1)
2. **GraphQL APIs**: Only REST JSON APIs (v1)
3. **Streaming Responses**: NDJSON, SSE (future enhancement)
4. **Complex Pagination**: Cursor-based, link-header (v1 does simple limit/offset)
5. **API Rate Limiting**: Advanced retry logic (use basic exponential backoff)
6. **Schema Validation**: Full OpenAPI schema validation (parse but don't enforce)

### 1.5 Example: Kalimat API

Let's use the Kalimat API (https://api.kalimat.dev/docs/) as our reference example:

**OpenAPI Spec**: Available at `/openapi.json` endpoint
**Search Endpoint**: `/search` (hypothetical - need to inspect actual spec)
**Authentication**: Bearer token (hypothetical)
**Response Structure**: (Need to inspect via test query)

```json
{
  "data": {
    "results": [
      {
        "id": "doc-123",
        "content": {
          "text": "The actual content here...",
          "highlight": "..."
        },
        "relevance_score": 0.95,
        "source": {
          "name": "Tafsir Ibn Kathir",
          "chapter": "Al-Fatiha"
        },
        "metadata": {
          "author": "Ibn Kathir",
          "date": "1373"
        }
      }
    ],
    "total": 42
  }
}
```

**Desired Generated Config**:

```yaml
kalimat:
  adapter: openapi
  api_key_env: KALIMAT_API_KEY
  options:
    # API configuration
    base_url: https://api.kalimat.dev
    endpoint: /search
    method: POST

    # Authentication
    auth:
      type: bearer
      header: Authorization
      scheme: Bearer

    # Request mapping (how to send query/top_k)
    request_body:
      query: "${query}"
      limit: ${top_k}

    # Response mapping (JMESPath expressions)
    response_mapping:
      # Path to results array
      results_array: "data.results"

      # Field mappings (JMESPath from each result item)
      fields:
        id: "id"
        text: "content.text"
        score: "relevance_score"
        source: "source.name"
        metadata: "{author: metadata.author, chapter: source.chapter}"
```

**Usage**:
```bash
# Generate the config
uv run ragdiff generate-adapter \
  --openapi-url https://api.kalimat.dev/openapi.json \
  --api-key $KALIMAT_API_KEY \
  --test-query "what is tawhid" \
  --adapter-name kalimat \
  --output configs/kalimat.yaml

# Use immediately
uv run ragdiff query "explain tawhid" --tool kalimat --config configs/kalimat.yaml
```

---

## 2. Architecture Design

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SPIDER: OpenAPI System                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Component 1: OpenAPIAdapter (Runtime)         │  │
│  │  - Reads config-based API definitions                │  │
│  │  - Executes HTTP requests with auth                  │  │
│  │  - Applies JMESPath response mappings                │  │
│  │  - Normalizes to RagResult                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓ uses                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │    Component 2: Response Mapping Engine (JMESPath)   │  │
│  │  - JMESPath evaluation for field extraction          │  │
│  │  - Template variable substitution (${query})         │  │
│  │  - Score normalization from various formats          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │     Component 3: OpenAPI Spec Parser                  │  │
│  │  - Fetch OpenAPI spec from URL                       │  │
│  │  - Parse OpenAPI 3.x JSON/YAML                       │  │
│  │  - Extract endpoints, schemas, auth                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ↓ used by                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │   Component 4: AI Configuration Generator (CLI)       │  │
│  │  - CLI: ragdiff generate-adapter                     │  │
│  │  - Uses Claude to identify search endpoint           │  │
│  │  - Makes test queries and analyzes responses         │  │
│  │  - Generates JMESPath mappings                       │  │
│  │  - Outputs validated YAML config                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Component Details

#### Component 1: OpenAPIAdapter (Runtime Adapter)

**File**: `src/ragdiff/adapters/openapi.py`

**Responsibilities**:
- Implement `RagAdapter` interface for generic OpenAPI calls
- Read adapter configuration from `options` dict
- Build HTTP requests from templates
- Apply JMESPath mappings to responses
- Normalize scores and create RagResult objects

**Key Methods**:
```python
class OpenAPIAdapter(RagAdapter):
    ADAPTER_NAME = "openapi"
    ADAPTER_API_VERSION = "1.0.0"

    def __init__(self, config: ToolConfig, credentials: dict[str, str] | None = None):
        """Initialize with config containing options dict."""

    def search(self, query: str, top_k: int = 5) -> list[RagResult]:
        """Execute search via OpenAPI endpoint and map response."""

    def _build_request(self, query: str, top_k: int) -> dict:
        """Build request with template substitution."""

    def _execute_request(self, request_data: dict) -> dict:
        """Execute HTTP request with retry logic."""

    def _map_response(self, response: dict) -> list[RagResult]:
        """Apply JMESPath mappings to extract RagResults."""
```

**Configuration Schema** (via `options` dict):

```python
{
    "base_url": str,              # Required: API base URL
    "endpoint": str,              # Required: Search endpoint path
    "method": str,                # Default: POST
    "auth": {                     # Required: Auth configuration
        "type": str,              # bearer, api_key, basic
        "header": str,            # Header name (e.g., Authorization)
        "scheme": str,            # Optional: Bearer, ApiKey
    },
    "request_body": dict,         # Template for request body
    "request_params": dict,       # Template for query params
    "response_mapping": {         # JMESPath mappings
        "results_array": str,     # Path to results array
        "fields": {
            "id": str,            # JMESPath for id
            "text": str,          # JMESPath for text
            "score": str,         # JMESPath for score
            "source": str,        # JMESPath for source
            "metadata": str,      # JMESPath object expression
        }
    }
}
```

#### Component 2: Response Mapping Engine

**File**: `src/ragdiff/adapters/openapi_mapping.py`

**Responsibilities**:
- Apply JMESPath expressions to extract fields
- Handle template variable substitution (`${query}`, `${top_k}`)
- Normalize scores from various formats (0-1, 0-100, 0-1000)
- Graceful error handling for missing fields

**Key Classes**:
```python
class TemplatEngine:
    """Handle ${var} substitution in request templates."""
    def render(self, template: dict, variables: dict) -> dict:
        pass

class ResponseMapper:
    """Apply JMESPath to extract RagResult fields."""
    def __init__(self, mapping_config: dict):
        pass

    def map_results(self, response: dict) -> list[RagResult]:
        """Extract and normalize results from response."""
        pass

    def _extract_field(self, item: dict, jmespath_expr: str) -> Any:
        """Extract single field using JMESPath."""
        pass

    def _normalize_score(self, score: float) -> float:
        """Normalize to 0-1 range."""
        pass
```

**JMESPath Examples**:
```python
# Simple path
"content.text" → item["content"]["text"]

# Array index
"results[0].title" → results[0]["title"]

# Object construction
"{author: metadata.author, date: published}"
→ {"author": item["metadata"]["author"], "date": item["published"]}

# Transformations
"results[?score > `0.8`].{text: content, score: score}"
→ Filter and transform
```

#### Component 3: OpenAPI Spec Parser

**File**: `src/ragdiff/openapi/parser.py`

**Responsibilities**:
- Fetch OpenAPI specs from URLs (handle redirects, JSON/YAML)
- Parse OpenAPI 3.0/3.1 specifications
- Extract endpoint metadata (paths, methods, parameters, schemas)
- Identify authentication schemes
- Provide structured data for AI analysis

**Key Classes**:
```python
class OpenAPISpec:
    """Parsed OpenAPI specification."""
    def __init__(self, spec_dict: dict):
        pass

    @classmethod
    def from_url(cls, url: str) -> "OpenAPISpec":
        """Fetch and parse OpenAPI spec from URL."""
        pass

    def get_endpoints(self) -> list[EndpointInfo]:
        """Return all API endpoints."""
        pass

    def get_auth_schemes(self) -> list[AuthScheme]:
        """Extract authentication requirements."""
        pass

@dataclass
class EndpointInfo:
    path: str
    method: str
    summary: str
    description: str
    parameters: list[dict]
    request_body_schema: dict | None
    response_schema: dict | None

@dataclass
class AuthScheme:
    type: str  # apiKey, http, oauth2
    name: str
    scheme: str  # bearer, basic
    location: str  # header, query, cookie
```

**Dependencies**:
- `pyyaml`: Parse YAML OpenAPI specs
- `requests`: Fetch specs from URLs
- `jsonschema` (optional): Validate spec structure

#### Component 4: AI Configuration Generator

**File**: `src/ragdiff/cli.py` (new command: `generate-adapter`)

**Responsibilities**:
- New Typer CLI command: `ragdiff generate-adapter`
- Interactive or automated workflow
- Uses Claude API to analyze specs and responses
- Generates valid YAML configuration
- Validates generated config with test query

**Command Interface**:
```bash
uv run ragdiff generate-adapter \
  --openapi-url URL \              # Required: OpenAPI spec URL
  --api-key KEY \                  # Required: API credentials
  --test-query "query" \           # Required: Test query string
  --adapter-name name \            # Required: Adapter name for config
  --output path/to/config.yaml \  # Optional: Output file (default: stdout)
  --endpoint /path \               # Optional: Specify endpoint (else AI selects)
  --method POST \                  # Optional: HTTP method (default: AI selects)
  --interactive                    # Optional: Interactive mode with confirmations
```

**Workflow**:
```python
def generate_adapter_config(
    openapi_url: str,
    api_key: str,
    test_query: str,
    adapter_name: str,
    endpoint: str | None = None,
    interactive: bool = False
) -> dict:
    """
    1. Fetch OpenAPI spec
    2. Parse spec to extract endpoints
    3. Use AI to identify search endpoint (or use provided)
    4. Make test query with provided credentials
    5. Use AI to analyze response and generate JMESPath mappings
    6. Construct YAML config
    7. Validate config by making another test query
    8. Return/save config
    """
    pass
```

**AI Prompts** (use Claude API):

**Prompt 1: Identify Search Endpoint**
```
Given this OpenAPI specification, identify which endpoint is most likely
the search/query endpoint for a RAG system.

OpenAPI endpoints:
{endpoint_list}

Respond with:
1. The endpoint path (e.g., /v1/search)
2. The HTTP method (GET/POST)
3. Brief reasoning

Format: JSON
```

**Prompt 2: Generate Response Mapping**
```
Given this API response from a search query, generate JMESPath expressions
to extract the required fields for a RAG result.

Required fields:
- id: Unique identifier (string)
- text: Main content text (string)
- score: Relevance score (float, should be 0-1)
- source: Source document/name (string, optional)
- metadata: Additional metadata (dict, optional)

API Response:
{json_response}

Generate JMESPath expressions for:
1. results_array: Path to the array of results
2. id: Extract id from each result
3. text: Extract main content text
4. score: Extract relevance score
5. source: Extract source name/identifier
6. metadata: Construct metadata object from available fields

Respond in JSON format with the mapping configuration.
```

**Output**: YAML file ready to use

```yaml
# Generated by: ragdiff generate-adapter
# OpenAPI Spec: https://api.kalimat.dev/openapi.json
# Generated: 2025-10-25T10:30:00Z

kalimat:
  adapter: openapi
  api_key_env: KALIMAT_API_KEY
  options:
    base_url: https://api.kalimat.dev
    endpoint: /v1/search
    method: POST

    auth:
      type: bearer
      header: Authorization
      scheme: Bearer

    request_body:
      query: "${query}"
      limit: ${top_k}

    response_mapping:
      results_array: "data.results"
      fields:
        id: "id"
        text: "content.text"
        score: "relevance_score"
        source: "source.name"
        metadata: "{author: metadata.author, chapter: source.chapter}"
```

### 2.3 Data Flow

**Runtime Flow** (using generated config):
```
User Query
    ↓
ragdiff query "what is tawhid" --tool kalimat
    ↓
Factory creates OpenAPIAdapter(config)
    ↓
OpenAPIAdapter.search(query, top_k)
    ↓
1. Build request from template
   - Substitute ${query} → "what is tawhid"
   - Substitute ${top_k} → 5
    ↓
2. Execute HTTP request
   - POST https://api.kalimat.dev/v1/search
   - Headers: Authorization: Bearer {api_key}
   - Body: {"query": "what is tawhid", "limit": 5}
    ↓
3. Parse JSON response
    ↓
4. Apply JMESPath mappings
   - Extract results array: response["data"]["results"]
   - For each result:
     - id = result["id"]
     - text = result["content"]["text"]
     - score = result["relevance_score"]
     - source = result["source"]["name"]
     - metadata = {author: result["metadata"]["author"], ...}
    ↓
5. Normalize scores (0-1 range)
    ↓
6. Create RagResult objects
    ↓
Return list[RagResult]
    ↓
Display to user
```

**Generator Flow** (creating config):
```
User Command
    ↓
ragdiff generate-adapter --openapi-url ... --api-key ... --test-query ...
    ↓
1. Fetch OpenAPI spec from URL
   - Handle JSON/YAML
   - Parse with openapi-core or custom parser
    ↓
2. Extract endpoints and auth info
   - Get all paths and methods
   - Get security schemes
    ↓
3. AI: Identify search endpoint
   - Send endpoint list to Claude
   - Get recommended endpoint + method
   - User can override with --endpoint flag
    ↓
4. Make test query
   - Build request with test query
   - Execute with provided API key
   - Capture full response
    ↓
5. AI: Analyze response structure
   - Send response JSON to Claude
   - Get JMESPath mappings for fields
   - Validate mappings make sense
    ↓
6. Construct config YAML
   - Build options dict
   - Add auth configuration
   - Add request/response mappings
    ↓
7. Validate config
   - Create OpenAPIAdapter with generated config
   - Make another test query
   - Verify results are valid RagResults
    ↓
8. Save or output config
   - Write to --output file or stdout
   - Add helpful comments
    ↓
Success message + usage instructions
```

### 2.4 Error Handling Strategy

**Configuration Errors** (fail fast):
- Missing required fields in `options` dict
- Invalid JMESPath expressions
- Missing authentication credentials
- Invalid base URL or endpoint

**Runtime Errors** (informative):
- Network failures (connection, timeout)
- HTTP errors (401, 404, 500)
- Response parsing errors (invalid JSON)
- JMESPath extraction failures (missing fields)

**Generator Errors** (helpful):
- Unable to fetch OpenAPI spec
- No suitable search endpoint found
- Test query failed (auth, network)
- AI cannot generate valid mappings
- Config validation failed

**Error Messages Should**:
- Clearly state what went wrong
- Suggest how to fix it
- Include relevant context (URL, endpoint, field name)
- Never expose sensitive credentials

---

## 3. Technical Decisions

### 3.1 Response Mapping: Why JMESPath?

**Options Considered**:
1. **JSONPath** (`$.data.results[*].text`)
   - Pro: Industry standard, widely known
   - Con: Limited transformations, no object construction

2. **Simple Dotted Paths** (`data.results.text`)
   - Pro: Easy to understand, no dependencies
   - Con: Cannot handle arrays, transformations, defaults

3. **JMESPath** (`data.results[*].{text: content, score: score}`)
   - Pro: Powerful transformations, object construction, filtering
   - Pro: Used by AWS CLI, Azure, industry standard
   - Pro: Excellent Python library (`jmespath`)
   - Con: Slightly more complex syntax

**Decision**: **JMESPath** for power and flexibility

**Examples**:
```python
# Simple extraction
"data.results[0].text"

# Array mapping
"data.results[*].text"

# Object construction
"data.results[*].{id: id, text: content, score: relevance}"

# Filtering
"data.results[?score > `0.8`]"

# Nested access with defaults
"data.results[*].metadata.author || 'Unknown'"
```

### 3.2 Authentication: Supported Schemes (v1)

**Supported**:
1. **Bearer Token** (most common for modern APIs)
   ```yaml
   auth:
     type: bearer
     header: Authorization
     scheme: Bearer
   ```

2. **API Key Header**
   ```yaml
   auth:
     type: api_key
     header: X-API-Key
   ```

3. **API Key Query Parameter**
   ```yaml
   auth:
     type: api_key
     param: api_key
   ```

4. **Basic Auth**
   ```yaml
   auth:
     type: basic
     username_env: API_USERNAME
     password_env: API_PASSWORD
   ```

**Not Supported** (v1):
- OAuth 2.0 flows (requires browser interaction)
- JWT refresh logic
- Custom authentication schemes

### 3.3 Request Building: Template Variables

**Supported Variables**:
- `${query}`: User's search query (string)
- `${top_k}`: Number of results (integer)

**Template Locations**:
- Request body (JSON)
- Query parameters
- Headers (for custom headers)

**Example**:
```yaml
request_body:
  q: "${query}"
  max_results: ${top_k}
  filter: "language:ar"

request_params:
  query: "${query}"
  limit: ${top_k}
```

**Rendering**:
```python
# Input template
{"q": "${query}", "max_results": ${top_k}}

# Variables
{"query": "what is tawhid", "top_k": 5}

# Output
{"q": "what is tawhid", "max_results": 5}
```

### 3.4 OpenAPI Parsing: Library Choice

**Options**:
1. **openapi-core**: Full validation, complex
2. **prance**: Good parser, handles refs
3. **Custom parser**: Simple dict walking

**Decision**: **Custom parser** for v1 (simple dict access)
- OpenAPI spec is just JSON/YAML
- We only need basic endpoint/schema info
- Avoid heavy dependencies
- Can upgrade to full parser later if needed

**Rationale**:
- Faster iteration, fewer dependencies
- Most OpenAPI specs are simple enough
- Focus on the 80% use case
- Parser library adds complexity without much value for our use case

### 3.5 AI Usage: When and How

**Use Claude API For**:
1. **Endpoint identification**: Which endpoint is the search endpoint?
   - Input: List of endpoints with summaries
   - Output: Recommended endpoint + reasoning

2. **Response mapping**: Generate JMESPath expressions
   - Input: Example API response JSON
   - Output: Mapping configuration

3. **Validation**: Does the generated config make sense?
   - Input: Generated config + test results
   - Output: Validation report + suggestions

**Do NOT Use AI For**:
- Request execution (just use requests library)
- JSON parsing (standard library)
- Template rendering (simple string substitution)

**AI Interaction Pattern**:
```python
async def analyze_response_with_ai(response: dict) -> dict:
    """Use LLM (via LiteLLM) to generate JMESPath mappings."""
    from litellm import acompletion

    prompt = f"""
    Analyze this API response and generate JMESPath expressions...
    Response: {json.dumps(response, indent=2)}
    """

    result = await acompletion(
        model="claude-3-5-sonnet-20241022",  # Can use any LiteLLM-supported model
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )

    return json.loads(result.choices[0].message.content)
```

### 3.6 Config Validation Strategy

**Two-Phase Validation**:

**Phase 1: Schema Validation** (in adapter `__init__`)
- Required fields present (`base_url`, `endpoint`, `auth`, `response_mapping`)
- Types correct (string, dict, etc.)
- JMESPath expressions are syntactically valid
- Auth configuration complete

**Phase 2: Runtime Validation** (during generation)
- Make actual test query
- Verify response matches expected structure
- Validate extracted fields are reasonable
- Ensure RagResult objects are created successfully

**Fail Fast**:
- Invalid config → `ConfigurationError` with clear message
- Don't try to "fix" config automatically
- User must provide valid config or regenerate

---

## 4. Implementation Phases

### Phase 1: Core OpenAPI Adapter (Foundation)

**Goal**: Basic adapter that works with manually written configs

**Tasks**:
1. Create `OpenAPIAdapter` class implementing `RagAdapter`
2. Implement request building with template substitution
3. Implement response mapping with JMESPath
4. Add authentication support (Bearer, API Key)
5. Write comprehensive tests with mock API

**Deliverable**:
- Can manually write a config YAML
- OpenAPIAdapter successfully queries API
- Returns valid RagResult objects

**Test Coverage**:
- Test with multiple mock API response structures
- Test all auth types
- Test error handling (network, parsing, missing fields)
- Test score normalization

**Files**:
- `src/ragdiff/adapters/openapi.py`
- `src/ragdiff/adapters/openapi_mapping.py`
- `tests/test_openapi_adapter.py`

### Phase 2: OpenAPI Spec Parser

**Goal**: Parse OpenAPI specs and extract useful metadata

**Tasks**:
1. Create `OpenAPISpec` class to represent parsed specs
2. Implement `from_url()` to fetch and parse specs
3. Extract endpoints, parameters, schemas
4. Extract authentication schemes
5. Handle both JSON and YAML specs
6. Write tests with real OpenAPI specs

**Deliverable**:
- Can fetch and parse OpenAPI specs from URLs
- Extract structured endpoint information
- Identify authentication requirements

**Test Coverage**:
- Test with Swagger Petstore (standard example)
- Test with custom OpenAPI 3.1 spec
- Test error handling (invalid URL, malformed spec)

**Files**:
- `src/ragdiff/openapi/parser.py`
- `src/ragdiff/openapi/__init__.py`
- `tests/test_openapi_parser.py`

### Phase 3: AI Configuration Generator (Automation)

**Goal**: CLI command that generates configs automatically

**Tasks**:
1. Add `generate-adapter` command to Typer CLI
2. Implement OpenAPI spec fetching
3. Integrate Claude API for endpoint identification
4. Make test queries to target API
5. Use Claude to analyze responses and generate mappings
6. Validate generated config
7. Output YAML with helpful comments
8. Add interactive mode for user confirmation

**Deliverable**:
- `uv run ragdiff generate-adapter` works end-to-end
- Generates valid, working configs
- Handles errors gracefully with helpful messages

**Test Coverage**:
- Integration tests with mock OpenAPI specs
- Mock Claude API responses
- Test error cases (invalid spec, failed query, no suitable endpoint)

**Files**:
- `src/ragdiff/cli.py` (add command)
- `src/ragdiff/openapi/generator.py`
- `tests/test_adapter_generator.py`

### Phase 4: Real-World Validation

**Goal**: Validate with actual APIs (Kalimat, others)

**Tasks**:
1. Generate config for Kalimat API
2. Test end-to-end with real queries
3. Identify edge cases and fix
4. Document any manual config adjustments needed
5. Add example configs to `configs/`
6. Update README with usage examples

**Deliverable**:
- At least 2 real APIs working via generated configs
- Documentation for common scenarios
- Known limitations documented

**Files**:
- `configs/kalimat.yaml` (example)
- `configs/another-api.yaml` (example)
- `README.md` (updated with examples)

### Phase 5: Documentation & Polish

**Goal**: Production-ready with full documentation

**Tasks**:
1. Update architecture doc (`codev/resources/arch.md`)
2. Add comprehensive docstrings
3. Add CLI help text
4. Create user guide for config generation
5. Add troubleshooting guide
6. Version bump and CHANGELOG

**Deliverable**:
- Full documentation
- Clean, polished user experience
- Ready for release

**Files**:
- `codev/resources/arch.md`
- `docs/openapi-adapter-guide.md` (new)
- `CHANGELOG.md`
- `src/ragdiff/version.py` (bump to 1.2.0)

---

## 5. Testing Strategy

### 5.1 Unit Tests

**OpenAPIAdapter**:
- Request building with templates
- Response mapping with JMESPath
- Score normalization
- Error handling (missing fields, invalid responses)
- All authentication types

**ResponseMapper**:
- JMESPath extraction for various structures
- Object construction
- Array handling
- Default values
- Graceful failures

**OpenAPISpec Parser**:
- Fetching specs from URLs
- Parsing JSON and YAML
- Extracting endpoints and auth
- Handling malformed specs

### 5.2 Integration Tests

**Generator End-to-End**:
- Mock OpenAPI spec → generated config → working adapter
- Real OpenAPI spec (Swagger Petstore) → generated config
- Test query → response analysis → JMESPath generation

**Real API Tests** (with real credentials):
- Kalimat API (if available)
- Use `@pytest.mark.integration` to skip in CI

### 5.3 Test Coverage Goals

- Unit tests: 90%+ coverage
- All error paths tested
- All authentication types tested
- All JMESPath patterns tested

### 5.4 Mock Strategy

**Mock APIs**:
```python
@pytest.fixture
def mock_api_server():
    """Local Flask/FastAPI server simulating various response structures."""
    # Return different structures for testing
    pass

@pytest.fixture
def mock_openapi_spec():
    """Sample OpenAPI 3.1 spec."""
    return {
        "openapi": "3.1.0",
        "paths": {
            "/search": {
                "post": {...}
            }
        }
    }
```

**Mock Claude API**:
```python
@pytest.fixture
def mock_claude_response():
    """Mock Claude API for endpoint identification and mapping."""
    return {
        "endpoint": "/search",
        "method": "POST",
        "mappings": {...}
    }
```

---

## 6. Dependencies

### 6.1 New Dependencies

**Required**:
- `jmespath` (^1.0.1): JMESPath implementation for Python
- `litellm` (^1.0.0): Unified LLM API client for AI generation (supports Anthropic, OpenAI, Azure, etc.)

**Optional**:
- `openapi-core` (future): If we want full OpenAPI validation
- `prance` (future): If we need reference resolution ($ref)

### 6.2 Existing Dependencies

Leverage existing:
- `requests`: HTTP requests
- `pydantic`: Configuration validation
- `pyyaml`: YAML parsing
- `typer`: CLI framework

---

## 7. Configuration Examples

### Example 1: Simple API with Bearer Auth

```yaml
simple-api:
  adapter: openapi
  api_key_env: SIMPLE_API_KEY
  options:
    base_url: https://api.simple.com
    endpoint: /v1/search
    method: POST

    auth:
      type: bearer
      header: Authorization
      scheme: Bearer

    request_body:
      query: "${query}"
      limit: ${top_k}

    response_mapping:
      results_array: "results"
      fields:
        id: "id"
        text: "text"
        score: "score"
        source: "source"
```

### Example 2: Complex Nested Response

```yaml
complex-api:
  adapter: openapi
  api_key_env: COMPLEX_API_KEY
  options:
    base_url: https://api.complex.com
    endpoint: /search
    method: POST

    auth:
      type: api_key
      header: X-API-Key

    request_body:
      q: "${query}"
      max_results: ${top_k}
      filters:
        language: "ar"

    response_mapping:
      results_array: "data.search_results.items"
      fields:
        id: "document.id"
        text: "document.content.full_text"
        score: "ranking.relevance_score"
        source: "document.metadata.source_name"
        metadata: "{author: document.metadata.author, date: document.metadata.published_date, tags: document.tags[*].name}"
```

### Example 3: GET Request with Query Params

```yaml
get-api:
  adapter: openapi
  api_key_env: GET_API_KEY
  options:
    base_url: https://api.getexample.com
    endpoint: /search
    method: GET

    auth:
      type: api_key
      param: apikey

    request_params:
      q: "${query}"
      limit: ${top_k}
      format: json

    response_mapping:
      results_array: "items"
      fields:
        id: "id"
        text: "snippet"
        score: "relevance"
        source: "title"
```

---

## 8. Success Metrics

### 8.1 Functional Metrics

- [ ] Generator creates working config for Kalimat API
- [ ] Generator creates working config for second API (different structure)
- [ ] Generated configs work without manual editing (90%+ success rate)
- [ ] All existing RAGDiff tests still pass
- [ ] New tests achieve 90%+ coverage

### 8.2 Performance Metrics

- [ ] Config generation completes in < 60 seconds
- [ ] OpenAPIAdapter overhead < 100ms per query
- [ ] JMESPath mapping overhead < 10ms per result

### 8.3 Usability Metrics

- [ ] User can generate config without reading documentation (intuitive CLI)
- [ ] Error messages are clear and actionable
- [ ] Generated YAML is readable with helpful comments

### 8.4 Quality Metrics

- [ ] All pre-commit hooks pass
- [ ] Full type hints (mypy clean)
- [ ] All docstrings present
- [ ] Architecture doc updated

---

## 9. Risks & Mitigations

### Risk 1: OpenAPI Specs Vary Widely

**Risk**: Real-world OpenAPI specs may not follow standards perfectly

**Mitigation**:
- Focus on well-formed specs initially
- Graceful degradation (log warnings, continue)
- Interactive mode lets users override AI decisions
- Document known limitations

### Risk 2: AI-Generated Mappings May Be Wrong

**Risk**: Claude might generate incorrect JMESPath expressions

**Mitigation**:
- Always validate with test query before saving config
- Show user the extracted results for confirmation
- Interactive mode for manual adjustment
- Save failed examples for improvement

### Risk 3: Authentication Complexity

**Risk**: Some APIs use complex auth (OAuth, custom schemes)

**Mitigation**:
- V1 only supports common auth types (Bearer, API Key)
- Document unsupported auth types
- Future enhancement for OAuth

### Risk 4: Response Structures Too Complex

**Risk**: Some APIs return deeply nested or unusual structures

**Mitigation**:
- JMESPath is powerful enough for most cases
- Allow manual config editing for edge cases
- Document common patterns
- Collect examples for improvement

---

## 10. Future Enhancements (Post-V1)

### 10.1 Advanced Features

1. **Pagination Support**
   - Cursor-based pagination
   - Link header pagination
   - Automatic multi-page fetching

2. **Streaming Responses**
   - NDJSON streaming
   - Server-Sent Events (SSE)

3. **GraphQL Support**
   - GraphQL query building
   - Response normalization

4. **OAuth 2.0**
   - Authorization code flow
   - Token refresh logic

### 10.2 AI Improvements

1. **Multi-Example Learning**
   - Generate config from multiple test queries
   - Learn patterns across responses

2. **Config Refinement**
   - Suggest improvements to existing configs
   - Optimize JMESPath expressions

3. **Automatic Testing**
   - Generate test queries
   - Validate config quality

### 10.3 Developer Experience

1. **Config Debugger**
   - Step through mapping process
   - Show intermediate values

2. **Visual Config Builder**
   - Web UI for building configs
   - Interactive JMESPath tester

3. **Config Registry**
   - Share configs for popular APIs
   - Community contributions

---

## 11. Open Questions

1. **Should we support async/await for HTTP requests?**
   - Pro: Better performance for concurrent queries
   - Con: Adds complexity
   - Decision: TBD (maybe v1.1)

2. **How to handle rate limiting?**
   - Should adapter implement backoff?
   - Or leave to user's retry logic?
   - Decision: Basic exponential backoff in v1

3. **Should we cache OpenAPI specs?**
   - Pro: Faster subsequent generations
   - Con: May get stale
   - Decision: No cache in v1, add later if needed

4. **Interactive vs. automated mode?**
   - Always ask for confirmation?
   - Or trust AI fully?
   - Decision: Both modes (default automated, `--interactive` flag)

---

## Next Steps

1. **Review this spec** with stakeholders
2. **Create implementation plan** (detailed task breakdown)
3. **Set up development branch**
4. **Begin Phase 1** (Core OpenAPI Adapter)

---

**End of Specification**
