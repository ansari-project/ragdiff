"""Mock demonstration of Kalimat API adapter generation.

This demonstrates what the generate-adapter command would produce
for the Kalimat API if we had network access.
"""

# Mock Kalimat OpenAPI spec (realistic structure)
KALIMAT_OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "Kalimat API",
        "version": "1.0.0",
        "description": "Islamic knowledge search API"
    },
    "servers": [
        {"url": "https://api.kalimat.dev", "description": "Production server"}
    ],
    "paths": {
        "/v1/search": {
            "post": {
                "summary": "Search Islamic texts",
                "description": "Full-text search across Islamic corpus",
                "operationId": "searchTexts",
                "tags": ["search"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "corpus": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "results": {
                                                    "type": "array",
                                                    "items": {"type": "object"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication"
            }
        }
    }
}

# Mock response from Kalimat API for test query "ما هو التوحيد"
KALIMAT_MOCK_RESPONSE = {
    "data": {
        "results": [
            {
                "id": "tafsir-001",
                "content": {
                    "text": "التوحيد هو إفراد الله بالعبادة...",
                    "arabic": "التوحيد هو إفراد الله بالعبادة",
                    "translation": "Tawhid is singling out Allah in worship..."
                },
                "relevance_score": 0.95,
                "source": {
                    "name": "تفسير ابن كثير",
                    "type": "tafsir",
                    "chapter": "الفاتحة",
                    "verse": "1"
                },
                "metadata": {
                    "author": "ابن كثير",
                    "author_latin": "Ibn Kathir",
                    "date_hijri": "774",
                    "category": "عقيدة"
                }
            },
            {
                "id": "hadith-042",
                "content": {
                    "text": "عن معاذ بن جبل قال: قال رسول الله صلى الله عليه وسلم...",
                    "arabic": "التوحيد حق الله على العباد",
                    "translation": "Tawhid is the right of Allah upon His servants..."
                },
                "relevance_score": 0.88,
                "source": {
                    "name": "صحيح البخاري",
                    "type": "hadith",
                    "collection": "البخاري",
                    "number": "2856"
                },
                "metadata": {
                    "grade": "صحيح",
                    "narrator": "معاذ بن جبل",
                    "category": "عقيدة"
                }
            }
        ],
        "total": 42,
        "query_time_ms": 125
    }
}

# What the AI would generate
AI_GENERATED_MAPPING = {
    "results_array": "data.results",
    "fields": {
        "id": "id",
        "text": "content.text",
        "score": "relevance_score",
        "source": "source.name",
        "metadata": "{author: metadata.author_latin, type: source.type, category: metadata.category, chapter: source.chapter}"
    }
}

# Final generated configuration
GENERATED_KALIMAT_CONFIG = {
    "kalimat": {
        "adapter": "openapi",
        "api_key_env": "KALIMAT_API_KEY",
        "timeout": 30,
        "max_retries": 3,
        "options": {
            "base_url": "https://api.kalimat.dev",
            "endpoint": "/v1/search",
            "method": "POST",
            "auth": {
                "type": "api_key",
                "header": "X-API-Key"
            },
            "request_body": {
                "query": "${query}",
                "limit": "${top_k}"
            },
            "response_mapping": AI_GENERATED_MAPPING
        }
    }
}


if __name__ == "__main__":
    import json
    print("=" * 80)
    print("MOCK DEMONSTRATION: Kalimat API Adapter Generation")
    print("=" * 80)

    print("\n📥 Step 1: Fetch OpenAPI Spec")
    print("   URL: https://api.kalimat.dev/openapi.json")
    print("   ✓ Spec parsed successfully")
    print(f"   API: {KALIMAT_OPENAPI_SPEC['info']['title']} v{KALIMAT_OPENAPI_SPEC['info']['version']}")

    print("\n🤖 Step 2: AI Identifies Search Endpoint")
    print("   AI Model: claude-3-5-sonnet-20241022")
    print("   ✓ Identified: POST /v1/search")
    print("   Reasoning: Endpoint named 'search' with query parameter in request body")

    print("\n🔐 Step 3: Determine Authentication")
    print("   ✓ Found auth scheme: ApiKeyAuth (API Key in header)")
    print("   Auth type: api_key")
    print("   Header: X-API-Key")

    print("\n🔍 Step 4: Make Test Query")
    print("   Query: 'ما هو التوحيد' (What is Tawhid?)")
    print("   ✓ Test query successful")
    print(f"   Got {len(KALIMAT_MOCK_RESPONSE['data']['results'])} results")

    print("\n🧠 Step 5: AI Generates Response Mapping")
    print("   AI analyzed response structure:")
    print(f"   ✓ Results array: {AI_GENERATED_MAPPING['results_array']}")
    print("   ✓ Field mappings:")
    for field, path in AI_GENERATED_MAPPING['fields'].items():
        print(f"      - {field}: {path}")

    print("\n✅ Step 6: Validate Configuration")
    print("   Creating OpenAPIAdapter with generated config...")
    print("   Making validation query...")
    print("   ✓ Validation successful - got 2 results")

    print("\n📝 Generated Configuration:")
    print("=" * 80)
    import yaml
    yaml_output = yaml.dump(GENERATED_KALIMAT_CONFIG, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(yaml_output)

    print("\n💡 Usage:")
    print("   export KALIMAT_API_KEY=your_api_key_here")
    print("   ragdiff query \"ما هو التوحيد\" --tool kalimat --config configs/kalimat.yaml")

    print("\n🎉 Mock demonstration complete!")
    print("   In production, this entire process takes ~30-60 seconds")
    print("=" * 80)
