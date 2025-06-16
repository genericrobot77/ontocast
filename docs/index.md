# OntoCast <img src="https://raw.githubusercontent.com/growgraph/ontocast/refs/heads/main/docs/assets/favicon.ico" alt="Agentic Ontology Triplecast logo" style="height: 32px; width:32px;"/>

### Agentic ontology assisted framework for semantic triple extraction from documents

![Python](https://img.shields.io/badge/python-3.12-blue.svg) 
[![PyPI version](https://badge.fury.io/py/ontocast.svg)](https://badge.fury.io/py/ontocast)
[![PyPI Downloads](https://static.pepy.tech/badge/ontocast)](https://pepy.tech/projects/ontocast)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![pre-commit](https://github.com/growgraph/ontocast/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/growgraph/ontocast/actions/workflows/pre-commit.yml)

## Overview

OntoCast is a powerful framework that automatically extracts semantic triples from documents using an agentic approach. It combines ontology management with natural language processing to create structured knowledge from unstructured text.

## Key Features

- **Ontology-Guided Extraction**: Uses ontologies to guide the extraction process and ensure semantic consistency
- **Entity Disambiguation**: Resolves entity and property references across chunks
- **Multi-Format Support**: Handles various input formats including text, JSON, PDF, and Markdown
- **Semantic Chunking**: Intelligent text chunking based on semantic similarity
- **MCP Compatibility**: Fully compatible with the Model Control Protocol (MCP) specification, providing standardized endpoints for health checks, info, and document processing
- **RDF Output**: Generates standardized RDF/Turtle output

### Extraction Steps

- **Document Processing**
    - Supports PDF, markdown, and text documents
    - Automated text chunking and processing

- 
- **Automated Ontology Management**
    - Intelligent ontology selection and construction
    - Multi-stage validation and critique system
    - Ontology sublimation and refinement

- **Knowledge Graph Integration**
    - RDF-based knowledge graph storage
    - Triple extraction for both ontologies and facts
    - Configurable workflow with visit limits
    - Chunk aggregation preserving fact lineage


## Installation

```sh
uv add ontocast 
# or
pip install ontocast
```

## Configuration


Create a `.env` file with your OpenAI API key:

```bash
cp .env.example .env
```


### Running the Server

```bash
uv run serve \
    --ontology-directory ONTOLOGY_DIR \
    --working-directory WORKING_DIR
```


### Process Endpoint

The `/process` endpoint accepts:
- `application/json`: JSON data
- `multipart/form-data`: File uploads

And returns:
- `application/json`: Processing results including:
  - Extracted facts in Turtle format
  - Generated ontology in Turtle format
  - Processing metadata


```bash
# Process a PDF file
curl -X POST http://url:port/process -F "file=@data/pdf/sample.pdf"

curl -X POST http://url:port/process -F "file=@test2/sample.json"

# Process text content
curl -X POST http://localhost:8999/process \
    -H "Content-Type: application/json" \
    -d '{"text": "Your document text here"}'
```

## MCP Endpoints

OntoCast implements the following MCP-compatible endpoints:

- `GET /health`: Health check endpoint
- `GET /info`: Service information endpoint
- `POST /process`: Document processing endpoint

### Processing Filesystem Documents

```bash
uv run serve \
    --ontology-directory ONTOLOGY_DIR \
    --working-directory WORKING_DIR \
    --input-path DOCUMENT_DIR
```


### NB
- json documents are expected to contain text in `text` field
- recursion_limit is calculated based on max_visits * estimated_chunks, the estimated number of chunks is taken to be 30 or otherwise fetched from `.env` (vie `ESTIMATED_CHUNKS`)   
- default 8999 is used default port


### Docker

To build docker
```sh
docker buildx build -t growgraph/ontocast:0.1.1 . 2>&1 | tee build.log
```

## Project Structure

```
src/
├── agent.py          # Main agent workflow implementation
├── onto.py           # Ontology and RDF graph handling
├── nodes/            # Individual workflow nodes
├── tools/            # Tool implementations
└── prompts/          # LLM prompts
```

## Workflow

The extraction follows a multi-stage workflow:

<img src="https://github.com/growgraph/ontocast/blob/main/docs/assets/graph.png?raw=True" alt="Workflow diagram" width="350" style="float: right; margin-left: 20px;"/>


1. **Document Preparation**
    - [Optional] Convert to Markdown
    - Text chunking

2. **Ontology Processing**
    - Ontology selection
    - Text to ontology triples
    - Ontology critique

3. **Fact Extraction**
    - Text to facts
    - Facts critique
    - Ontology sublimation

4. **Chunk Normalization**
    - Chunk KG aggregation
    - Entity/Property Disambiguation

5. **Storage**
    - Knowledge graph storage



## Documentation

Full documentation is available at: [growgraph.github.io/ontocast](https://growgraph.github.io/ontocast)


## Roadmap

1. Add a triple store for serialization/ontology management
2. Replace graph to text by a symbolic graph interface (agent tools for working with triples) 


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses RDFlib for semantic triple management
- Uses docling for pdf/pptx conversion
- Uses OpenAI language models / open models served via Ollama for fact extraction
- Uses langchain/langgraph
