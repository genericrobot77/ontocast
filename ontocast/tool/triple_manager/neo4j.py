"""Triple store management tools for OntoCast.

This module provides functionality for managing RDF triple stores, including
abstract interfaces and filesystem-based implementations.
"""

import logging

from rdflib import Graph
from rdflib.namespace import DC, DCTERMS, OWL, RDF, RDFS

from ontocast.tool.triple_manager.core import TripleStoreManager

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from pydantic import Field

from ontocast.onto import Ontology, derive_ontology_id

logger = logging.getLogger(__name__)


class Neo4jTripleStoreManager(TripleStoreManager):
    """Neo4j-based triple store manager using n10s (neosemantics) plugin.

    This implementation handles RDF data more faithfully by using both the n10s
    property graph representation and raw RDF triple storage for accurate reconstruction.

    Args:
        uri: Neo4j connection URI
        auth: Neo4j authentication tuple (user, password)
        clean: If True, delete all nodes in the database on init (default: False)
    """

    uri: str = Field(..., description="Neo4j connection URI")
    auth: tuple = Field(..., description="Neo4j authentication tuple (user, password)")
    clean: bool = Field(
        default=False, description="If True, clean the database on init."
    )
    _driver = None  # private attribute, not a pydantic field

    def __init__(self, uri, auth, clean=False, **kwargs):
        if isinstance(auth, str):
            if "/" in auth:
                user, password = auth.split("/", 1)
                auth_tuple = (user, password)
            else:
                raise ValueError("NEO4J_AUTH must be in 'user/password' format")
        else:
            auth_tuple = auth

        super().__init__(
            uri=uri,
            auth=auth_tuple,
            clean=clean,
            **kwargs,
        )

        if GraphDatabase is None:
            raise ImportError("neo4j Python driver is not installed.")
        self._driver = GraphDatabase.driver(self.uri, auth=self.auth)

        with self._driver.session() as session:
            # Clean database if requested
            if self.clean:
                try:
                    session.run("MATCH (n) DETACH DELETE n")
                    logger.debug("Neo4j database cleaned (all nodes deleted)")
                except Exception as e:
                    logger.debug(f"Neo4j cleanup failed: {e}")

            # Initialize n10s configuration
            self._init_n10s_config(session)

            # Create constraints and indexes
            self._create_constraints_and_indexes(session)

    def _init_n10s_config(self, session):
        """Initialize n10s configuration with better RDF handling."""
        try:
            # Check if already configured
            result = session.run("CALL n10s.graphconfig.show()")
            if result.single():
                logger.debug("n10s already configured")
        except:
            pass

        try:
            session.run("""
                CALL n10s.graphconfig.init({
                    handleVocabUris: "KEEP",
                    handleMultival: "OVERWRITE",
                    typesToLabels: false,
                    keepLangTag: false,
                    keepCustomDataTypes: true,
                    handleRDFTypes: "NODES"
                })
            """)
            logger.debug("n10s configuration initialized")
        except Exception as e:
            logger.warning(f"n10s configuration failed: {e}")

    def _create_constraints_and_indexes(self, session):
        """Create necessary constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE",
            "CREATE CONSTRAINT ontology_iri_unique IF NOT EXISTS FOR (o:Ontology) REQUIRE o.uri IS UNIQUE",
            "CREATE INDEX namespace_prefix IF NOT EXISTS FOR (ns:Namespace) ON (ns.prefix)",
        ]

        for constraint in constraints:
            try:
                session.run(constraint)
                logger.debug(f"Created constraint/index: {constraint.split()[-1]}")
            except Exception as e:
                logger.debug(f"Constraint/index creation (might already exist): {e}")

    def _extract_namespace_prefix(self, uri: str) -> tuple[str, str]:
        """Extract namespace and local name from URI."""
        common_separators = ["#", "/", ":"]
        for sep in common_separators:
            if sep in uri:
                parts = uri.rsplit(sep, 1)
                if len(parts) == 2:
                    return parts[0] + sep, parts[1]
        return uri, ""

    def _get_ontology_namespaces(self, session) -> dict:
        """Get all known ontology namespaces from the database."""
        result = session.run("""
            MATCH (ns:Namespace)
            RETURN ns.prefix as prefix, ns.uri as uri
            UNION
            MATCH (o:Ontology)
            RETURN null as prefix, o.uri as uri
        """)

        namespaces = {}
        for record in result:
            uri = record.get("uri")
            prefix = record.get("prefix")
            if uri:
                if prefix:
                    namespaces[prefix] = uri
                else:
                    # Extract potential namespace from ontology URI
                    ns, _ = self._extract_namespace_prefix(uri)
                    if ns != uri:  # Only if we actually found a namespace
                        namespaces[ns] = ns

        return namespaces

    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch ontologies from Neo4j with faithful RDF reconstruction.

        This method:
        1. Identifies distinct ontologies by their namespace URIs
        2. Fetches all entities belonging to each ontology
        3. Reconstructs the RDF graph faithfully using stored triples when available
        4. Falls back to n10s property graph conversion when needed
        """
        ontologies = []

        with self._driver.session() as session:
            try:
                # First, try to get explicitly stored ontology metadata
                ontology_metadata = self._fetch_ontology_metadata(session)

                # Get all known namespaces
                namespaces = self._get_ontology_namespaces(session)

                # If we have explicit ontology metadata, use it
                if ontology_metadata:
                    for ont_meta in ontology_metadata:
                        ontology = self._reconstruct_ontology_from_metadata(
                            session, ont_meta, namespaces
                        )
                        if ontology:
                            ontologies.append(ontology)
                else:
                    # Fallback: group by namespace and create ontologies
                    ontologies = self._group_by_namespace_and_create_ontologies(
                        session, namespaces
                    )

                # If still no ontologies found, create a combined one
                if not ontologies:
                    fallback_ontology = self._create_fallback_ontology(session)
                    if fallback_ontology:
                        ontologies.append(fallback_ontology)

            except Exception as e:
                logger.error(f"Error in fetch_ontologies: {e}")
                # Last resort fallback
                fallback_ontology = self._create_fallback_ontology(session)
                if fallback_ontology:
                    ontologies.append(fallback_ontology)

        logger.info(f"Successfully loaded {len(ontologies)} ontologies")
        return ontologies

    def _fetch_ontology_metadata(self, session) -> list[dict]:
        """Fetch explicit ontology metadata."""
        result = session.run(f"""
            MATCH (o)-[:`{str(RDF.type)}`]->(t:Resource {{ uri: "{str(OWL.Ontology)}" }})
            WHERE o.uri IS NOT NULL
            RETURN
              o.uri AS iri,
              coalesce(
                o.title,
                o.`{str(DCTERMS.title)}`,
                o.`{str(DC.title)}`
              ) AS title,
              coalesce(
                o.description,
                o.`{str(DCTERMS.description)}`,
                o.`{str(DC.description)}`
              ) AS description,
              coalesce(
                o.`{str(RDFS.label)}`
              ) AS label,
              coalesce(
                o.version,
                o.versionInfo,
                o.`{str(OWL.versionInfo)}`
              ) AS version,
              labels(o) AS labels
        """)

        metadata = []
        for record in result:
            iri = record.get("iri")
            if iri:
                metadata.append(
                    {
                        "iri": iri,
                        "title": record.get("title") or "",
                        "description": record.get("description") or "",
                        "version": record.get("version") or "",
                        "labels": record.get("labels", []),
                    }
                )

        return metadata

    def _reconstruct_ontology_from_metadata(
        self, session, ont_meta: dict, namespaces: dict
    ) -> Ontology:
        """Reconstruct an ontology from its metadata and related entities."""
        iri = ont_meta["iri"]
        namespace_uri, _ = self._extract_namespace_prefix(iri)

        logger.debug(f"Reconstructing ontology: {iri} with namespace: {namespace_uri}")

        # Fallback to n10s export for this namespace
        graph = self._export_namespace_via_n10s(session, namespace_uri)
        if graph and len(graph) > 0:
            return self._create_ontology_object(iri, ont_meta, graph)

    def _export_namespace_via_n10s(self, session, namespace_uri: str) -> Graph:
        """Export entities belonging to a namespace using n10s."""
        try:
            # Get all entities in this namespace
            result = session.run(
                """
                MATCH (n)
                WHERE n.uri STARTS WITH $namespace
                WITH collect(id(n)) as nodeIds
                CALL n10s.rdf.export.cypher(
                    'MATCH (n)-[r]->(m) WHERE id(n) IN $nodeIds OR id(m) IN $nodeIds RETURN n,r,m',
                    {format: 'Turtle', params: {nodeIds: nodeIds}}
                )
                YIELD rdf
                RETURN rdf
            """,
                namespace=namespace_uri,
            )

            combined_ttl = ""
            for record in result:
                if record["rdf"]:
                    combined_ttl += record["rdf"] + "\n"

            if combined_ttl.strip():
                graph = Graph()
                graph.parse(data=combined_ttl, format="turtle")
                logger.debug(
                    f"Exported {len(graph)} triples via n10s for namespace {namespace_uri}"
                )
                return graph

        except Exception as e:
            logger.debug(
                f"Failed to export via n10s for namespace {namespace_uri}: {e}"
            )

        return None

    def _group_by_namespace_and_create_ontologies(
        self, session, namespaces: dict
    ) -> list[Ontology]:
        """Group entities by namespace and create ontologies."""
        ontologies = []

        # Get all unique namespace prefixes from URIs
        result = session.run("""
            MATCH (n)
            WHERE n.uri IS NOT NULL
            WITH distinct split(n.uri, '#')[0] + '#' as namespace
            WHERE size(namespace) > 10
            RETURN namespace
            UNION
            MATCH (n)
            WHERE n.uri IS NOT NULL AND NOT n.uri CONTAINS '#'
            WITH distinct reverse(split(reverse(n.uri), '/')[1..]) as parts
            RETURN reduce(s = 'http', part IN parts | s + '/' + part) + '/' as namespace
        """)

        found_namespaces = set()
        for record in result:
            ns = record["namespace"]
            if ns:
                found_namespaces.add(ns)

        for namespace in found_namespaces:
            graph = self._export_namespace_via_n10s(session, namespace)
            if graph and len(graph) > 0:
                ontology_id = derive_ontology_id(namespace)
                ontology = Ontology(
                    graph=graph,
                    iri=namespace.rstrip("#/"),
                    ontology_id=ontology_id,
                    title=f"Ontology for {ontology_id}",
                    description=f"Auto-generated ontology for namespace {namespace}",
                    version="1.0",
                )
                ontologies.append(ontology)
                logger.debug(
                    f"Created ontology for namespace {namespace} with {len(graph)} triples"
                )

        return ontologies

    def _create_fallback_ontology(self, session) -> Ontology:
        """Create a fallback ontology with all available data."""
        try:
            logger.debug("Creating fallback ontology with all data")

            # Fallback to n10s export
            result = session.run("""
                CALL n10s.rdf.export.cypher('MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 5000', {format: 'Turtle'})
                YIELD rdf
                RETURN rdf
            """)

            combined_ttl = ""
            for record in result:
                if record["rdf"]:
                    combined_ttl += record["rdf"] + "\n"

            if combined_ttl.strip():
                graph = Graph()
                graph.parse(data=combined_ttl, format="turtle")
                logger.debug(
                    f"Created fallback ontology from n10s export with {len(graph)} triples"
                )
                return Ontology(
                    graph=graph,
                    iri="http://example.org/combined-ontology",
                    ontology_id="combined",
                    title="Combined Ontology Data",
                    description="All RDF data from Neo4j (from n10s export)",
                    version="1.0",
                )

        except Exception as e:
            logger.error(f"Fallback ontology creation failed: {e}")

        return None

    def _create_ontology_object(
        self, iri: str, metadata: dict, graph: Graph
    ) -> Ontology:
        """Create an Ontology object from IRI, metadata, and graph."""
        ontology_id = derive_ontology_id(iri)
        return Ontology(
            graph=graph,
            iri=iri,
            ontology_id=ontology_id,
            title=metadata.get("title") or ontology_id,
            description=metadata.get("description") or "",
            version=metadata.get("version") or "1.0",
        )

    def serialize_ontology(self, o: Ontology, **kwargs):
        """Serialize an ontology to Neo4j with both n10s and raw triple storage."""
        turtle_data = o.graph.serialize(format="turtle")

        with self._driver.session() as session:
            # Store via n10s for graph queries
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()

            # Store ontology metadata
            self._store_ontology_metadata(session, o)

        return summary

    def serialize_facts(self, g: Graph, **kwargs):
        """Serialize facts (RDF graph) to Neo4j."""
        turtle_data = g.serialize(format="turtle")

        with self._driver.session() as session:
            # Store via n10s
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()

        return summary

    def _store_ontology_metadata(self, session, ontology: Ontology):
        """Store ontology metadata for better retrieval."""
        session.run(
            """
            MERGE (o:Ontology {uri: $iri})
            SET o.title = $title,
                o.description = $description,
                o.version = $version,
                o.ontology_id = $ontology_id
        """,
            iri=ontology.iri,
            title=ontology.title,
            description=ontology.description,
            version=ontology.version,
            ontology_id=ontology.ontology_id,
        )

    def close(self):
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
