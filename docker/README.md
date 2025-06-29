# Docker Setup for OntoCast Triple Stores

This directory contains Docker Compose configurations for running triple stores that are compatible with OntoCast.

## Quick Start

### Apache Fuseki (Recommended)

Fuseki is the recommended triple store for OntoCast due to its native RDF support.

**Setup:**
1. Copy the example environment file and customize it:
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

2. Start Fuseki:
```bash
cd docker/fuseki
docker compose --profile test.fuseki up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop Fuseki
docker compose down
```

**Access Fuseki:**
- Web Interface: http://localhost:3032
- Default Dataset: `/test`
- SPARQL Endpoint: http://localhost:3032/test/sparql

### Neo4j with n10s Plugin

Neo4j can be used as an alternative triple store with RDF capabilities via the n10s plugin.

**Setup:**
1. Copy the example environment file and customize it:
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

2. Start Neo4j:
```bash
cd docker/neo4j
docker compose --profile test.sem.neo4j up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop Neo4j
docker compose down
```

**Access Neo4j:**
- Browser: http://localhost:7476
- Username: `neo4j`
- Password: `test!passfortesting`
- Bolt Connection: `bolt://localhost:7689`

## Environment Configuration

After starting your preferred triple store, configure OntoCast by setting environment variables in your `.env` file:

### For Fuseki
```bash
FUSEKI_URI=http://localhost:3032/test
FUSEKI_AUTH=admin/abc123-qwe
```

### For Neo4j
```bash
NEO4J_URI=bolt://localhost:7689
NEO4J_AUTH=neo4j/test!passfortesting
```

## Data Persistence

Both Docker Compose configurations use named volumes to persist data:

- **Fuseki**: `fuseki_data` and `fuseki_config` volumes
- **Neo4j**: `neo4j_data`, `neo4j_logs`, `neo4j_import`, and `neo4j_plugins` volumes

To backup your data:

```bash
# Backup Fuseki data
docker run --rm -v ontocast-fuseki_fuseki_data:/data -v $(pwd):/backup alpine tar czf /backup/fuseki-backup.tar.gz -C /data .

# Backup Neo4j data
docker run --rm -v ontocast-neo4j_neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .
```

## Health Checks

Both configurations include health checks to ensure the services are running properly:

- **Fuseki**: Checks the ping endpoint
- **Neo4j**: Verifies database connectivity

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :3032  # For Fuseki
   lsof -i :7476  # For Neo4j
   
   # Stop conflicting services
   docker compose down
   ```

2. **Authentication Issues**
   ```bash
   # Reset Neo4j password
   docker exec -it test.sem.neo4j cypher-shell -u neo4j -p neo4j
   # Then change password in the shell
   ```

3. **Plugin Not Loaded (Neo4j)**
   ```bash
   # Check if n10s plugin is loaded
   docker exec -it test.sem.neo4j cypher-shell -u neo4j -p test!passfortesting "CALL n10s.graphconfig.show()"
   ```

### Logs and Debugging

```bash
# View Fuseki logs
cd docker/fuseki
docker compose logs -f

# View Neo4j logs
cd docker/neo4j
docker compose logs -f

# Check container status
docker ps
```

## Performance Tuning

### Fuseki
- Default configuration uses in-memory storage
- For production, consider persistent storage with TDB2

### Neo4j
- Memory settings are configured for development
- For production, adjust heap and pagecache sizes based on available RAM

## Security Notes

- Default configurations use simple passwords for development
- For production, use strong passwords and consider network isolation
- Never expose triple stores directly to the internet without proper authentication

# how to build Dockerfile

# to run containers from docker compose

```shell
docker compose --env-file .env up <container_spec> -d
```

# to stop containers from docker compose

```shell
docker compose stop <container_name> 
```

# to bash into a container

```shell
docker exec -it <containter_name> sh
```



## neo4j shell

Neo4j web interface [http://localhost:NEO4J_PORT](http://localhost:7476). NB: the standard neo4j port is 7474.