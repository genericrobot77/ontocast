"""Triple store management tools for OntoCast.

This module provides functionality for managing RDF triple stores, including
abstract interfaces and filesystem-based implementations.
"""

import logging
from typing import Optional

from rdflib.namespace import OWL, RDF

from ontocast.tool.triple_manager.core import TripleStoreManagerWithAuth

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from pydantic import Field

from ontocast.onto import Ontology, RDFGraph, derive_ontology_id

logger = logging.getLogger(__name__)


class Neo4jTripleStoreManager(TripleStoreManagerWithAuth):
    """Neo4j-based triple store manager using n10s (neosemantics) plugin.

    This implementation handles RDF data more faithfully by using both the n10s
    property graph representation and raw RDF triple storage for accurate reconstruction.

    Args:
        uri: Neo4j connection URI
        auth: Neo4j authentication tuple (user, password)
        clean: If True, delete all nodes in the database on init (default: False)
    """

    clean: bool = Field(
        default=False, description="If True, clean the database on init."
    )
    _driver = None  # private attribute, not a pydantic field

    def __init__(self, uri=None, auth=None, clean=False, **kwargs):
        super().__init__(
            uri=uri, auth=auth, env_uri="NEO4J_URI", env_auth="NEO4J_AUTH", **kwargs
        )
        self.clean = clean
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
                ontology_iris = self._fetch_ontology_iris(session)

                if ontology_iris:
                    for ont_iri in ontology_iris:
                        ontology = self._reconstruct_ontology_from_metadata(
                            session, ont_iri
                        )
                        if ontology:
                            ontologies.append(ontology)

            except Exception as e:
                logger.error(f"Error in fetch_ontologies: {e}")

        logger.info(f"Successfully loaded {len(ontologies)} ontologies")
        return ontologies

    def _fetch_ontology_iris(self, session) -> list[str]:
        """Fetch explicit ontology metadata."""
        result = session.run(f"""
            MATCH (o)-[:`{str(RDF.type)}`]->(t:Resource {{ uri: "{str(OWL.Ontology)}" }})
            WHERE o.uri IS NOT NULL
            RETURN
              o.uri AS iri
        """)

        iris = []
        for record in result:
            iri = record.get("iri", None)
            iris += [iri]
        iris = [iri for iri in iris if iri is not None]
        return iris

    def _reconstruct_ontology_from_metadata(self, session, iri) -> Optional[Ontology]:
        """Reconstruct an ontology from its metadata and related entities."""
        namespace_uri, _ = self._extract_namespace_prefix(iri)

        logger.debug(f"Reconstructing ontology: {iri} with namespace: {namespace_uri}")

        # Fallback to n10s export for this namespace
        graph = self._export_namespace_via_n10s(session, namespace_uri)
        if graph and len(graph) > 0:
            return self._create_ontology_object(iri, iri, graph)

    def _export_namespace_via_n10s(
        self, session, namespace_uri: str
    ) -> Optional[RDFGraph]:
        """Export entities belonging to a namespace using n10s."""
        try:
            result = session.run(
                f"""
                CALL n10s.rdf.export.cypher(
                    'MATCH (n)-[r]->(m) WHERE n.uri STARTS WITH "{namespace_uri}" RETURN n,r,m',
                    {{format: 'Turtle'}}
                )
                YIELD subject, predicate, object, isLiteral, literalType, literalLang
                RETURN subject, predicate, object, isLiteral, literalType, literalLang
                """
            )

            # Process into Turtle format
            turtle_lines = []

            for record in result:
                subj = record["subject"]
                pred = record["predicate"]
                obj = record["object"]
                is_literal = record["isLiteral"]
                literal_type = record["literalType"]
                literal_lang = record["literalLang"]

                # Format object
                if is_literal:
                    # Escape special characters in literals
                    obj = obj.replace('"', r"\"")
                    obj_str = f'"{obj}"'

                    # Add datatype or language tag if present
                    if literal_lang:
                        obj_str += f"@{literal_lang}"
                    elif literal_type:
                        obj_str += f"^^<{literal_type}>"
                else:
                    obj_str = f"<{obj}>"

                # Format triple
                turtle_lines.append(f"<{subj}> <{pred}> {obj_str} .")

            # Combine into single string
            turtle_string = "\n".join(turtle_lines)

            if turtle_string.strip():
                graph = RDFGraph()
                graph.parse(data=turtle_string, format="turtle")
                logger.debug(
                    f"Exported {len(graph)} triples via n10s for namespace {namespace_uri}"
                )
                return graph
            return None

        except Exception as e:
            logger.debug(
                f"Failed to export via n10s for namespace {namespace_uri}: {e}"
            )

        return None

    def _create_ontology_object(
        self, iri: str, metadata: dict, graph: RDFGraph
    ) -> Ontology:
        """Create an Ontology object from IRI, metadata, and graph."""
        ontology_id = derive_ontology_id(iri)
        return Ontology(graph=graph, iri=iri, ontology_id=ontology_id)

    def serialize_ontology(self, o: Ontology, **kwargs):
        """Serialize an ontology to Neo4j with both n10s and raw triple storage."""
        turtle_data = o.graph.serialize(format="turtle")

        with self._driver.session() as session:
            # Store via n10s for graph queries
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()

        return summary

    def serialize_facts(self, g: RDFGraph, **kwargs):
        """Serialize facts (RDF graph) to Neo4j."""
        turtle_data = g.serialize(format="turtle")

        with self._driver.session() as session:
            # Store via n10s
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()

        return summary

    def close(self):
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
