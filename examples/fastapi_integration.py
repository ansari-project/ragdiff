"""FastAPI integration example for RAGDiff.

This example demonstrates how to use RAGDiff in a production web service
with thread-safe concurrent request handling.

Features:
- Thread-safe concurrent query processing
- Proper error handling and validation
- Structured JSON responses
- Health check endpoint
- Configuration validation on startup

Run with:
    uvicorn examples.fastapi_integration:app --reload
"""

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# RAGDiff imports
from ragdiff import (
    compare,
    get_available_adapters,
    query,
    run_batch,
    validate_config,
)
from ragdiff.core.errors import (
    AdapterError,
    ConfigurationError,
    EvaluationError,
    ValidationError,
)

# Configuration
CONFIG_FILE = "config.yaml"  # Update to your config file path

# FastAPI app
app = FastAPI(
    title="RAGDiff API",
    description="Compare and evaluate RAG systems via REST API",
    version="1.0.0",
)


# Request/Response Models
class QueryRequest(BaseModel):
    """Single query request."""

    query: str = Field(..., min_length=1, description="Search query")
    tool: str = Field(..., description="RAG tool to query")
    top_k: int = Field(5, ge=1, le=100, description="Number of results")


class CompareRequest(BaseModel):
    """Comparison request."""

    query: str = Field(..., min_length=1, description="Search query")
    tools: Optional[list[str]] = Field(
        None, description="Tools to compare (None = all)"
    )
    top_k: int = Field(5, ge=1, le=100, description="Number of results per tool")
    parallel: bool = Field(True, description="Run searches in parallel")
    evaluate: bool = Field(False, description="Run LLM evaluation")


class BatchRequest(BaseModel):
    """Batch query request."""

    queries: list[str] = Field(..., min_length=1, description="List of queries")
    tools: Optional[list[str]] = Field(None, description="Tools to use (None = all)")
    top_k: int = Field(5, ge=1, le=100, description="Results per query")
    parallel: bool = Field(True, description="Run searches in parallel")
    evaluate: bool = Field(False, description="Run LLM evaluation")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    config_valid: bool
    available_adapters: list[str]


# Startup event - validate configuration
@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    try:
        validate_config(CONFIG_FILE)
        print(f"✓ Configuration valid: {CONFIG_FILE}")
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
        raise


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and configuration."""
    try:
        validate_config(CONFIG_FILE)
        config_valid = True
    except ConfigurationError:
        config_valid = False

    adapters = get_available_adapters()

    return HealthResponse(
        status="healthy" if config_valid else "degraded",
        config_valid=config_valid,
        available_adapters=list(adapters.keys()),
    )


# Get available adapters
@app.get("/adapters")
async def list_adapters():
    """List all available RAG adapters with metadata."""
    try:
        adapters = get_available_adapters()
        return {"adapters": adapters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# Single query endpoint
@app.post("/query")
async def query_endpoint(request: QueryRequest):
    """Query a single RAG system.

    Example:
        POST /query
        {
            "query": "What is RAG?",
            "tool": "vectara",
            "top_k": 5
        }
    """
    try:
        results = query(
            CONFIG_FILE,
            query_text=request.query,
            tool=request.tool,
            top_k=request.top_k,
        )

        # Convert to dict for JSON response
        return {
            "query": request.query,
            "tool": request.tool,
            "results": [
                {
                    "id": r.id,
                    "text": r.text,
                    "score": r.score,
                    "source": r.source,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }

    except ConfigurationError as e:
        raise HTTPException(
            status_code=400, detail=f"Configuration error: {str(e)}"
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except AdapterError as e:
        raise HTTPException(status_code=500, detail=f"Adapter error: {str(e)}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


# Compare endpoint
@app.post("/compare")
async def compare_endpoint(request: CompareRequest):
    """Compare multiple RAG systems on a single query.

    Example:
        POST /compare
        {
            "query": "What is RAG?",
            "tools": ["vectara", "goodmem"],
            "top_k": 5,
            "parallel": true,
            "evaluate": true
        }
    """
    try:
        comparison = compare(
            CONFIG_FILE,
            query_text=request.query,
            tools=request.tools,
            top_k=request.top_k,
            parallel=request.parallel,
            evaluate=request.evaluate,
        )

        # Convert to dict for JSON response
        return comparison.to_dict()

    except ConfigurationError as e:
        raise HTTPException(
            status_code=400, detail=f"Configuration error: {str(e)}"
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except AdapterError as e:
        raise HTTPException(status_code=500, detail=f"Adapter error: {str(e)}") from e
    except EvaluationError as e:
        raise HTTPException(
            status_code=500, detail=f"Evaluation error: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


# Batch endpoint
@app.post("/batch")
async def batch_endpoint(request: BatchRequest):
    """Run multiple queries against multiple RAG systems.

    Example:
        POST /batch
        {
            "queries": ["What is RAG?", "What is vector search?"],
            "tools": ["vectara", "goodmem"],
            "top_k": 5,
            "parallel": true,
            "evaluate": false
        }
    """
    try:
        results = run_batch(
            CONFIG_FILE,
            queries=request.queries,
            tools=request.tools,
            top_k=request.top_k,
            parallel=request.parallel,
            evaluate=request.evaluate,
        )

        # Convert to list of dicts for JSON response
        return {
            "queries": request.queries,
            "results": [comparison.to_dict() for comparison in results],
        }

    except ConfigurationError as e:
        raise HTTPException(
            status_code=400, detail=f"Configuration error: {str(e)}"
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=400, detail=f"Validation error: {str(e)}"
        ) from e
    except AdapterError as e:
        raise HTTPException(status_code=500, detail=f"Adapter error: {str(e)}") from e
    except EvaluationError as e:
        raise HTTPException(
            status_code=500, detail=f"Evaluation error: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


# Root endpoint
@app.get("/")
async def root():
    """API information."""
    return {
        "name": "RAGDiff API",
        "version": "1.0.0",
        "description": "Compare and evaluate RAG systems via REST API",
        "endpoints": {
            "health": "GET /health",
            "adapters": "GET /adapters",
            "query": "POST /query",
            "compare": "POST /compare",
            "batch": "POST /batch",
            "docs": "GET /docs",
        },
    }


# Example usage (if running directly)
if __name__ == "__main__":
    import uvicorn

    print("Starting RAGDiff API server...")
    print("API docs available at: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000)
