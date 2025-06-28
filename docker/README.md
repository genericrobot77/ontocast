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