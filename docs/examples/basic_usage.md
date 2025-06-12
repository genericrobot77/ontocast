# Basic Usage

This guide explains how to use OntoCast to process documents and extract structured knowledge.

## Starting the Server

The OntoCast server is started using the `uv run serve` command with required parameters:

```bash
uv run serve \
    --env-path .env \
    --working-directory WORKING_DIR \
    --ontology-directory ONTO_DIR \
    --llm-provider openai \
    --model-name gpt-4o-mini \
    --temperature 0.0 \
    --head-chunks 2 \
    --port 8999 \
    --logging-level info \
    --max-visits 3
```

### Required Parameters

- `--env-path`: Path to the environment file containing API keys
- `--working-directory`: Directory for temporary files and working data
- `--ontology-directory`: Directory containing ontology files

### Optional Parameters

- `--llm-provider`: LLM provider to use (default: openai)
- `--model-name`: Model name to use (default: gpt-4o-mini)
- `--temperature`: Temperature for LLM generation (default: 0.0)
- `--head-chunks`: Number of chunks to process at start
- `--port`: Server port (default: 8999)
- `--logging-level`: Logging level (debug, info, warning, error)
- `--max-visits`: Maximum visits per node (default: 3)

## Processing Workflow

The document processing follows this workflow:

1. **Convert to Markdown**: Convert input document to markdown format
2. **Chunk Text**: Split text into manageable chunks
3. **Select Ontology**: Choose appropriate ontology for the content
4. **Text to Ontology**: Extract ontological concepts
5. **Text to Facts**: Extract factual information
6. **Sublimate Ontology**: Refine and enhance the ontology
7. **Criticise Ontology**: Validate ontology structure
8. **Criticise Facts**: Validate extracted facts
9. **Aggregate Facts**: Combine facts from all chunks

## API Endpoints

### Process Document

You can send documents to the server in three ways:

1. **Using Multipart Form Data (for files)**:
```bash
# For PDF files
curl -X POST http://localhost:8999/process \
    -F "file=@path/to/your/document.pdf"

# For Markdown files
curl -X POST http://localhost:8999/process \
    -F "file=@path/to/your/document.md"

# For JSON files
curl -X POST http://localhost:8999/process \
    -F "file=@path/to/your/document.json"
```

2. **Using JSON (for text content)**:
```bash
curl -X POST http://localhost:8999/process \
    -H "Content-Type: application/json" \
    -d '{
        "text": "Your document text here"
    }'
```

3. **Using JSON File with Content-Type**:
```bash
curl -X POST http://localhost:8999/process \
    -H "Content-Type: application/json" \
    -d @path/to/your/document.json
```

### Response Format

```json
{
    "facts": [...],
    "ontology": {...},
    "status": "success"
}
```

## Error Handling

The server returns appropriate HTTP status codes:

- 200: Success
- 400: Bad Request (missing text or file)
- 500: Internal Server Error

## Environment Setup

Create a `.env` file with required API keys:

```bash
OPENAI_API_KEY=your_api_key_here
LLM_BASE_URL=optional_base_url
```

## Next Steps

- Explore [Advanced Usage](advanced_usage.md) for more complex scenarios
- Check [API Reference](../reference/index.md) for detailed API documentation
- Read [Best Practices](../user_guide/best_practices.md) for optimal usage 