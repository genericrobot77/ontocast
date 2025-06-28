"""Triple store management tools for OntoCast.

This module provides functionality for managing RDF triple stores, including
abstract interfaces and filesystem-based implementations.
"""

import abc
import logging
import pathlib
from typing import Optional

from rdflib import Graph

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None

from pydantic import Field

from ontocast.onto import Ontology, derive_ontology_id

from .onto import Tool

logger = logging.getLogger(__name__)


class TripleStoreManager(Tool):
    """Base class for managing RDF triple stores.

    This class defines the interface for triple store management operations,
    including fetching and storing ontologies and their graphs.

    """

    def __init__(self, **kwargs):
        """Initialize the triple store manager.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)

    @abc.abstractmethod
    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch all available ontologies.

        Returns:
            list[Ontology]: List of available ontologies.
        """
        return []

    @abc.abstractmethod
    def serialize_ontology(self, o: Ontology, **kwargs):
        """Store an ontology in the triple store.

        Args:
            o: The ontology to store.
            **kwargs: Additional keyword arguments for serialization.
        """
        pass

    @abc.abstractmethod
    def serialize_facts(self, g: Graph, **kwargs):
        """Store a graph with a given name.

        Args:
            g: The graph to store.
            **kwargs: Additional keyword arguments for serialization.
        """
        pass


class FilesystemTripleStoreManager(TripleStoreManager):
    """Filesystem-based implementation of triple store management.

    This class provides a concrete implementation of triple store management
    using the local filesystem for storage.

    Attributes:
        working_directory: Path to the working directory for storing data.
        ontology_path: Optional path to the ontology directory.
    """

    working_directory: pathlib.Path
    ontology_path: Optional[pathlib.Path]

    def __init__(self, **kwargs):
        """Initialize the filesystem triple store manager.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)

    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch all available ontologies from the filesystem.

        Returns:
            list[Ontology]: List of available ontologies.
        """
        ontologies = []
        if self.ontology_path is not None:
            sorted_files = sorted(self.ontology_path.glob("*.ttl"))
            for fname in sorted_files:
                try:
                    ontology = Ontology.from_file(fname)
                    ontologies.append(ontology)
                except Exception as e:
                    logging.error(f"Failed to load ontology {fname}: {str(e)}")
        return ontologies

    def serialize_ontology(self, o: Ontology, **kwargs):
        """Store an ontology in the filesystem.

        Args:
            o: The ontology to store.
            **kwargs: Additional keyword arguments for serialization.
        """
        fname = f"ontology_{o.ontology_id}_{o.version}"
        o.graph.serialize(
            format="turtle", destination=self.working_directory / f"{fname}.ttl"
        )

    def serialize_facts(self, g: Graph, **kwargs):
        """Store a graph in the filesystem.

        Args:
            g: The graph to store.
            **kwargs: Additional keyword arguments for serialization.
                spec: Optional specification for the filename.
        """
        spec = kwargs.pop("spec", None)
        if spec is None:
            fname = "current.ttl"
        elif isinstance(spec, str):
            s = spec.split("/")[-2:]
            s = "_".join([x for x in s if x])
            fname = f"facts_{s}.ttl"
        else:
            raise TypeError(f"string expected for spec {spec}")
        filename = self.working_directory / fname
        g.serialize(format="turtle", destination=filename)


class Neo4jTripleStoreManager(TripleStoreManager):
    """Neo4j-based triple store manager using n10s (neosemantics) plugin.
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
        super().__init__(uri=uri, auth=auth_tuple, clean=clean, **kwargs)
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
            try:
                session.run("""CALL n10s.graphconfig.init(
                            {
                              handleVocabUris: "MAP",
                              handleMultival: "OVERWRITE",
                              typesToLabels: false,
                              keepLangTag: false,
                              keepCustomDataTypes: true}
                            )""")
            except:
                pass
            try:
                session.run(
                    "CREATE CONSTRAINT n10s_unique_uri FOR (r:Resource) REQUIRE r.uri IS UNIQUE"
                )
                logger.debug("Created n10s URI constraint")
            except Exception as e:
                logger.debug(f"Constraint creation (might already exist): {e}")

    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch ontologies from Neo4j.

        This method looks for RDF data that represents ontologies and reconstructs
        the Ontology objects with their associated graphs.
        """
        ontologies = []

        with self._driver.session() as session:
            try:
                result = session.run("""
                MATCH (o:Ontology)
                RETURN o.uri as iri,
                    o.title as title,
                    o.description as description,
                    o.versionInfo as version,
                    o.label as label,
                    o.comment as comment
                """)

                ontology_iris = []
                for record in result:
                    iri = record.get("iri")
                    if iri:
                        title = (
                            record.get("title")
                            or record.get("dc_title")
                            or record.get("rdfs_label")
                            or ""
                        )

                        description = (
                            record.get("description")
                            or record.get("rdfs_comment")
                            or ""
                        )

                        ontology_iris.append(
                            {
                                "iri": iri,
                                "title": title,
                                "description": description,
                                "version": record.get("version") or "",
                            }
                        )

                # For each ontology IRI, export the related RDF data
                for ont_info in ontology_iris:
                    iri = ont_info["iri"]
                    logger.debug(f"Processing ontology: {iri}")

                    try:
                        export_result = session.run("""
                            CALL n10s.rdf.export.cypher('MATCH (n)-[r]->(m)
                                RETURN n,r,m',
                                {format: 'Turtle'})
                            YIELD rdf
                            RETURN rdf
                        """)

                        # Combine all RDF data
                        combined_ttl = ""
                        for exp_record in export_result:
                            if exp_record["rdf"]:
                                combined_ttl += exp_record["rdf"] + "\n"

                        if combined_ttl.strip():
                            # Parse the combined TTL data
                            g = Graph()
                            try:
                                g.parse(data=combined_ttl, format="turtle")
                                logger.debug(
                                    f"Parsed {len(g)} triples for ontology {iri}"
                                )

                                # Extract short name from IRI
                                ontology_id = derive_ontology_id(self.iri)

                                ontologies.append(
                                    Ontology(
                                        graph=g,
                                        iri=iri,
                                        ontology_id=ontology_id,
                                        title=ont_info["title"] or ontology_id,
                                        description=ont_info["description"] or "",
                                        version=ont_info["version"] or "",
                                    )
                                )
                            except Exception as parse_error:
                                logger.debug(
                                    f"Failed to parse TTL for {iri}: {parse_error}"
                                )
                                logger.debug(
                                    f"TTL data preview: {combined_ttl[:200]}..."
                                )
                        else:
                            logger.debug(f"No RDF data found for ontology {iri}")

                    except Exception as export_error:
                        logger.debug(f"Failed to export data for {iri}: {export_error}")

            except Exception as e:
                logger.debug(f"Error in fetch_ontologies: {e}")
                # Fallback: create a single ontology with all data
                try:
                    logger.debug(
                        "Attempting fallback: exporting all data as single ontology"
                    )
                    export_result = session.run("""
                        CALL n10s.rdf.export.cypher('MATCH (n)-[r]->(m)
                            RETURN n,r,m LIMIT 1000',
                            {format: 'Turtle'})
                        YIELD rdf
                        RETURN rdf
                    """)

                    combined_ttl = ""
                    for exp_record in export_result:
                        if exp_record["rdf"]:
                            combined_ttl += exp_record["rdf"] + "\n"

                    if combined_ttl.strip():
                        g = Graph()
                        g.parse(data=combined_ttl, format="turtle")
                        ontologies.append(
                            Ontology(
                                graph=g,
                                iri="http://example.org/combined-ontology",
                                ontology_id="combined",
                                title="Combined Ontology Data",
                                description="All RDF data from Neo4j",
                                version="1.0",
                            )
                        )
                        logger.debug(f"Created fallback ontology with {len(g)} triples")
                except Exception as fallback_error:
                    logger.debug(f"Fallback also failed: {fallback_error}")

        logger.debug(f"Successfully loaded {len(ontologies)} ontologies")
        return ontologies

    def serialize_ontology(self, o: Ontology, **kwargs):
        turtle_data = o.graph.serialize(format="turtle")
        with self._driver.session() as session:
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()
        return summary

    def serialize_facts(self, g: Graph, **kwargs):
        turtle_data = g.serialize(format="turtle")
        with self._driver.session() as session:
            result = session.run(
                "CALL n10s.rdf.import.inline($ttl, 'Turtle')", ttl=turtle_data
            )
            summary = result.single()
        return summary
