# OntoCast Workflow

This document describes the workflow of OntoCast's document processing pipeline.

## Overview

The OntoCast workflow consists of several stages that transform input documents into structured knowledge:

1. **Document Conversion**
   - Input documents are converted to markdown format
   - Supports various input formats (PDF, DOCX, TXT, MD)

2. **Text Chunking**
   - Documents are split into manageable chunks
   - Chunks are processed sequentially
   - Head chunks are processed first to establish context

3. **Ontology Processing**
   - **Selection**: Choose appropriate ontology for content
   - **Extraction**: Extract ontological concepts from text
   - **Sublimation**: Refine and enhance the ontology
   - **Criticism**: Validate ontology structure and relationships

4. **Fact Processing**
   - **Extraction**: Extract factual information from text
   - **Criticism**: Validate extracted facts
   - **Aggregation**: Combine facts from all chunks

## Detailed Flow

### 1. Document Input
- Accepts text or file input
- Converts to markdown format
- Preserves document structure

### 2. Text Processing
- Splits text into chunks
- Processes head chunks first
- Maintains context between chunks

### 3. Ontology Management
- Selects relevant ontology
- Extracts new concepts
- Validates relationships
- Refines structure

### 4. Fact Extraction
- Identifies entities
- Extracts relationships
- Validates facts
- Combines information

### 5. Output Generation
- Produces RDF graph
- Generates ontology
- Provides extracted facts

## Configuration Options

The workflow can be configured through command-line parameters:

- `--head-chunks`: Number of chunks to process first
- `--max-visits`: Maximum visits per node

## Best Practices

1. **Chunk Size**
   - Keep chunks manageable
   - Consider context preservation
   - Balance between detail and processing time

2. **Ontology Selection**
   - Choose appropriate ontology
   - Consider domain specificity
   - Allow for ontology evolution

3. **Fact Validation**
   - Validate extracted facts
   - Check for consistency
   - Handle contradictions

4. **Resource Management**
   - Monitor memory usage
   - Control processing time
   - Handle large documents

## Next Steps

- Check [API Reference](../reference/onto.md) 