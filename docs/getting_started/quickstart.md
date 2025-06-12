# Quick Start

This guide will help you get started with OntoCast quickly. We'll walk through a simple example of processing a document and viewing the results.

## Prerequisites

- OntoCast installed (see [Installation](installation.md))
- A sample document to process (e.g., a Markdown file)

## Basic Example

### 1. Start the Server

First, start the OntoCast server:

```bash
uv run serve \
    --working-directory ~/work/tmp/cwd \
    --logging-level info \
    --head-chunks 2 \
    --ontology-directory data/ontologies \
    --max-visits 2
```

### 2. Prepare a Sample Document

Create a simple Markdown file named `sample.md`:

```markdown
# Sample Document

This is a sample document about a person named John Doe.

John Doe is a software engineer who works at Example Corp.
He specializes in Python development and has 10 years of experience.
```

### 3. Process the Document

Send the document to the server for processing:

```bash
curl -X POST http://localhost:8000/process \
    -H "Content-Type: application/json" \
    -d '{
        "file_path": "sample.md",
        "format": "md"
    }'
```

### 4. View the Results

After processing, you can view the extracted information:

```bash
# Get the RDF graph
curl -X GET http://localhost:8000/graph/{document_id}

# Get the triples
curl -X GET http://localhost:8000/triples/{document_id}
```

## Expected Output

The server will return an RDF graph containing information about John Doe, including:

- Person entity
- Job role
- Company
- Skills
- Experience

## Understanding the Results

The processed document is converted into an RDF graph with:

1. **Entities**: People, organizations, concepts
2. **Properties**: Relationships between entities
3. **Values**: Specific information about entities

## Next Steps

Now that you've processed your first document, you can:

1. Try processing different types of documents (PDF, Word)
2. Explore the [Basic Usage](examples/basic_usage.md) guide
3. Learn about [Configuration](configuration.md) options
4. Check the [API Reference](reference/core.md) for more details 