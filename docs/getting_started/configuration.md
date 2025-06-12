# Configuration

This guide explains how to configure OntoCast to suit your needs.

## Command Line Options

### Server Configuration

```bash
uv run serve \
    --working-directory <path> \     # Working directory for temporary files
    --logging-level <level> \        # Logging level (debug, info, warning, error)
    --head-chunks <number> \         # Number of chunks to process at start
    --ontology-directory <path> \    # Directory containing ontology files
    --max-visits <number> \          # Maximum visits for processing nodes
    --port <number> \                # Server port (default: 8000)
    --host <address> \               # Server host (default: localhost)
    --timeout <seconds> \            # Processing timeout
    --memory-limit <mb> \            # Memory limit in megabytes
```

### Processing Options

```bash
uv run serve \
    --chunk-size <number> \          # Size of text chunks
    --min-chunk-size <number> \      # Minimum chunk size
    --max-chunk-size <number> \      # Maximum chunk size
```

## Environment Variables

You can also configure OntoCast using environment variables:

```bash
export ONTOCAST_WORKING_DIR=/path/to/working/dir
export ONTOCAST_LOG_LEVEL=info
export ONTOCAST_HEAD_CHUNKS=2
export ONTOCAST_ONTOLOGY_DIR=/path/to/ontologies
export ONTOCAST_MAX_VISITS=2
export ONTOCAST_PORT=8000
export ONTOCAST_HOST=localhost
export ONTOCAST_TIMEOUT=300
export ONTOCAST_MEMORY_LIMIT=1024
```

## Configuration File

Create a `config.yaml` file in your working directory:

```yaml
server:
  working_directory: /path/to/working/dir
  logging_level: info
  head_chunks: 2
  ontology_directory: /path/to/ontologies
  max_visits: 2
  port: 8000
  host: localhost
  timeout: 300
  memory_limit: 1024

processing:
  chunk_size: 1000
  overlap: 100
  min_chunk_size: 500
  max_chunk_size: 2000
  language: en
  model: gpt-3.5-turbo

ontologies:
  default: http://example.org/ontology
  prefixes:
    rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
    rdfs: http://www.w3.org/2000/01/rdf-schema#
    owl: http://www.w3.org/2002/07/owl#
```

## Logging Configuration

Configure logging in `logging.yaml`:

```yaml
version: 1
formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    level: INFO
  file:
    class: logging.FileHandler
    formatter: standard
    filename: ontocast.log
    level: DEBUG
root:
  level: INFO
  handlers: [console, file]
```

## Best Practices

1. **Working Directory**
   - Use an absolute path
   - Ensure sufficient disk space
   - Set appropriate permissions

2. **Memory Management**
   - Set reasonable memory limits
   - Monitor memory usage
   - Adjust chunk sizes accordingly

3. **Logging**
   - Use appropriate log levels
   - Rotate log files
   - Monitor disk space

4. **Security**
   - Restrict server access
   - Use secure connections
   - Validate input data

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Check directory permissions
   - Verify user access rights
   - Use appropriate ownership

2. **Memory Issues**
   - Reduce chunk sizes
   - Increase memory limit
   - Monitor system resources

3. **Timeout Errors**
   - Increase timeout value
   - Optimize processing
   - Check system load

## Next Steps

- Explore [Basic Usage](examples/basic_usage.md)
- Check [API Reference](reference/core.md)
- Read [Best Practices](user_guide/best_practices.md) 