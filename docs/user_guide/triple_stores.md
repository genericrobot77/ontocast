# Triple Store Configuration

OntoCast supports multiple triple store backends for storing and managing RDF data. This guide covers the setup and configuration of supported triple stores.

## Overview

OntoCast supports the following triple store backends:

1. **Apache Fuseki** (Recommended) - Native RDF triple store with SPARQL support
2. **Neo4j with n10s plugin** - Graph database with RDF capabilities
3. **Filesystem** - Local file-based storage (fallback)

When multiple triple stores are configured, OntoCast uses the following priority order:
1. Fuseki (if `FUSEKI_URI` and `FUSEKI_AUTH` are set)
2. Neo4j (if `NEO4J_URI` and `NEO4J_AUTH` are set)
3. Filesystem (default fallback)

## Environment Variables

Configure your triple store connection using environment variables in your `.env` file:

```bash
# Fuseki Configuration (Preferred)
FUSEKI_URI=http://localhost:3032/test
FUSEKI_AUTH=admin/abc123-qwe

# Neo4j Configuration (Alternative)
NEO4J_URI=bolt://localhost:7689
NEO4J_AUTH=neo4j/test!passfortesting

# Server Configuration
PORT=8999
RECURSION_LIMIT=1000
ESTIMATED_CHUNKS=30
```

## Apache Fuseki Setup

Apache Fuseki is the recommended triple store for OntoCast due to its native RDF support, SPARQL capabilities, and excellent performance with semantic data.

### Using Docker Compose

Copy the example environment file and customize it:

```bash
# For Fuseki
cd docker/fuseki
cp .env.example .env
# Edit .env if needed
```

The `.env` file should contain:
```bash
# docker/fuseki/.env
IMAGE_VERSION=secoresearch/fuseki:5.1.0
ENVIRONMENT_ACTUAL=test
CONTAINER_NAME="${ENVIRONMENT_ACTUAL}.fuseki"
STORE_FOLDER="$HOME/tmp/${CONTAINER_NAME}"
TS_PORT=3032
TS_PASSWORD="abc123-qwe"
TS_USERNAME="admin"
UID=1000
GID=1000
```

The Docker Compose file (`docker/fuseki/docker-compose.yml`) is already configured to use these environment variables.

### Starting Fuseki

```bash
# Navigate to fuseki directory
cd docker/fuseki

# Start Fuseki
docker compose --env-file .env fuseki up -d

# Check status
docker ps -a

# Stop Fuseki
docker compose stop test.fuseki
```

### Accessing Fuseki

- **Web Interface**: http://localhost:3032
- **Default Dataset**: `/test`
- **SPARQL Endpoint**: http://localhost:3032/test/sparql
- **Dataset Management**: http://localhost:3032/$/datasets

### Fuseki Features

- **Native RDF Support**: Direct storage of RDF triples
- **SPARQL 1.1**: Full SPARQL query language support
- **Named Graphs**: Support for multiple named graphs
- **REST API**: Comprehensive REST API for data management
- **Performance**: Optimized for semantic data operations

## Neo4j with n10s Plugin Setup

Neo4j can be used as an alternative triple store with the n10s (neosemantics) plugin, which provides RDF capabilities within the Neo4j graph database.

### Using Docker Compose

Copy the example environment file and customize it:

```bash
# For Neo4j
cd docker/neo4j
cp .env.example .env
# Edit .env if needed
```

The `.env` file should contain:
```bash
# docker/neo4j/.env
IMAGE_VERSION=neo4j:5.20
SPEC=test
CONTAINER_NAME="${SPEC}.sem.neo4j"
NEO4J_PORT=7476
NEO4J_BOLT_PORT=7689
STORE_FOLDER="$HOME/tmp/${CONTAINER_NAME}"
NEO4J_PLUGINS='["apoc", "graph-data-science", "n10s"]'
NEO4J_AUTH="neo4j/test!passfortesting"
```

The Docker Compose file (`docker/neo4j/docker-compose.yml`) is already configured to use these environment variables.

### Starting Neo4j

```bash
# Navigate to neo4j directory
cd docker/neo4j

# Start Neo4j
docker compose --env-file .env neo4j up -d

# Stop Neo4j
docker stop test.sem.neo4j
```

### Accessing Neo4j

- **Browser**: http://localhost:7476
- **Username**: `neo4j`
- **Password**: `test!passfortesting`
- **Bolt Connection**: `bolt://localhost:7689`

### Neo4j Features

- **Graph Database**: Native graph data model
- **n10s Plugin**: RDF import/export capabilities
- **Cypher Query Language**: Powerful graph querying
- **Visualization**: Built-in graph visualization
- **Scalability**: Enterprise-grade scalability

## Filesystem Storage

When no triple store is configured, OntoCast falls back to filesystem storage. This mode stores ontologies and facts as Turtle files in the working directory.

### Configuration

```bash
# No triple store environment variables needed
# OntoCast will use filesystem storage automatically
```

### Filesystem Features

- **Simple Setup**: No additional services required
- **Portable**: Easy to backup and transfer
- **Human Readable**: Turtle files can be inspected directly
- **Development Friendly**: Ideal for development and testing

## Triple Store Comparison

| Feature | Fuseki | Neo4j + n10s | Filesystem |
|---------|--------|--------------|------------|
| **RDF Native** | ✅ Yes | ⚠️ Via plugin | ✅ Yes |
| **SPARQL** | ✅ Full 1.1 | ❌ Limited | ❌ No |
| **Setup Complexity** | ✅ Simple | ⚠️ Moderate | ✅ Very Simple |
| **Visualization** | ⚠️ Basic | ✅ Excellent | ❌ None |
| **Production Ready** | ✅ Yes | ✅ Yes | ❌ No |

## Best Practices

### For Development
- Use **Filesystem** storage for quick setup and testing
- Use **Fuseki** for RDF-focused development

### For Production
- Use **Fuseki** for semantic data applications
- Use **Neo4j** if you need advanced graph analytics

### Configuration Tips
- Always set `FUSEKI_AUTH` or `NEO4J_AUTH` for security
- Use health checks in Docker Compose for reliability
- Monitor triple store performance and logs
- Backup your data regularly

## Troubleshooting

### Fuseki Issues
```bash
# Check if Fuseki is running
curl http://localhost:3032/$/ping


# Restart Fuseki
docker compose restart fuseki
```

### Neo4j Issues
```bash
# Check if Neo4j is running
curl http://localhost:7476

# Check n10s plugin
cypher-shell -u neo4j -p test!passfortesting "CALL n10s.graphconfig.show()"
```

### Common Problems
- **Connection Refused**: Triple store not running
- **Authentication Failed**: Incorrect credentials
- **Dataset Not Found**: Dataset not created in Fuseki
- **Plugin Not Loaded**: n10s plugin not installed in Neo4j 