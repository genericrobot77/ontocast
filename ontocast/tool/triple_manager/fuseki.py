import logging
from typing import Optional

import requests
from pydantic import Field
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

from ontocast.onto import Ontology, derive_ontology_id
from ontocast.tool.triple_manager.core import TripleStoreManagerWithAuth

logger = logging.getLogger(__name__)


class FusekiTripleStoreManager(TripleStoreManagerWithAuth):
    """Fuseki-based triple store manager."""

    dataset: Optional[str] = Field(default=None, description="Fuseki dataset name")

    def __init__(self, uri=None, auth=None, dataset=None, **kwargs):
        super().__init__(
            uri=uri, auth=auth, env_uri="FUSEKI_URI", env_auth="FUSEKI_AUTH", **kwargs
        )
        self.dataset = dataset
        self.init_dataset(self.dataset)
        if self.dataset is None:
            raise ValueError("Dataset must be specified in FUSEKI_URI or as argument")

    def init_dataset(self, dataset_name):
        fuseki_admin_url = f"{self.uri}/$/datasets"

        payload = {"dbName": dataset_name, "dbType": "tdb2"}

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(
            fuseki_admin_url, data=payload, headers=headers, auth=self.auth
        )

        if response.status_code == 200 or response.status_code == 201:
            logger.info(f"Dataset '{dataset_name}' created successfully.")
        else:
            logger.error(f"Failed to upload data. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")

    def _parse_dataset_from_uri(self, uri: str) -> Optional[str]:
        parts = uri.rstrip("/").split("/")
        if len(parts) > 0:
            return parts[-1]
        return None

    def _get_dataset_url(self):
        return f"{self.uri}/{self.dataset}"

    def fetch_ontologies(self) -> list[Ontology]:
        """Fetch all named graphs that contain an entity of type owl:Ontology."""
        sparql_url = f"{self._get_dataset_url()}/sparql"
        # Find all named graphs with an entity of type owl:Ontology
        query = f"""
        SELECT DISTINCT ?g ?s WHERE {{
            GRAPH ?g {{ ?s <{RDF.type}> <{OWL.Ontology}> }}
        }}
        """
        response = requests.post(
            sparql_url,
            data={"query": query, "format": "application/sparql-results+json"},
            auth=self.auth,
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch graphs from Fuseki: {response.text}")
            return []
        results = response.json()
        # Map: graph_uri -> set of ontology subjects
        graph_ontologies = {}
        for binding in results.get("results", {}).get("bindings", []):
            graph_uri = binding["g"]["value"]
            subj = binding["s"]["value"]
            graph_ontologies.setdefault(graph_uri, set()).add(subj)
        ontologies = []
        for graph_uri, ontology_subjects in graph_ontologies.items():
            # Download the graph as turtle
            graph = Graph()
            export_url = f"{self._get_dataset_url()}/get?graph={graph_uri}"
            export_resp = requests.get(
                export_url, auth=self.auth, headers={"Accept": "text/turtle"}
            )
            if export_resp.status_code == 200:
                graph.parse(data=export_resp.text, format="turtle")
                # For each ontology subject, create an Ontology object
                for onto_iri in ontology_subjects:
                    onto_iri_ref = URIRef(onto_iri)
                    # Only include if the triple is present
                    if (onto_iri_ref, RDF.type, OWL.Ontology) in graph:
                        ontology_id = derive_ontology_id(onto_iri)
                        ontologies.append(
                            Ontology(
                                graph=graph,
                                iri=onto_iri,
                                ontology_id=ontology_id,
                                title=f"Ontology for {ontology_id}",
                                description=f"Imported from Fuseki graph {graph_uri}",
                                version="1.0",
                            )
                        )
            else:
                logger.warning(f"Failed to fetch graph {graph_uri}: {export_resp.text}")
        return ontologies

    def serialize_ontology(self, o: Ontology, **kwargs):
        """Store an ontology as a named graph in Fuseki."""
        turtle_data = o.graph.serialize(format="turtle")
        graph_uri = o.iri or f"urn:ontology:{o.ontology_id}"
        url = f"{self._get_dataset_url()}/data"
        headers = {"Content-Type": "text/turtle;charset=utf-8"}
        response = requests.put(url, headers=headers, data=turtle_data, auth=self.auth)
        if response.status_code in (200, 201, 204):
            logger.info(f"Ontology {graph_uri} uploaded to Fuseki.")
            return True
        else:
            logger.error(
                f"Failed to upload ontology {graph_uri}. Status code: {response.status_code}"
            )
            logger.error(f"Response: {response.text}")
            return False

    def serialize_facts(self, g: Graph, **kwargs):
        """Store facts (RDF graph) in the default graph in Fuseki."""
        turtle_data = g.serialize(format="turtle")
        url = f"{self._get_dataset_url()}/data"
        headers = {"Content-Type": "text/turtle;charset=utf-8"}
        response = requests.post(url, headers=headers, data=turtle_data, auth=self.auth)
        if response.status_code in (200, 201, 204):
            logger.info("Facts uploaded to Fuseki default graph.")
            return True
        else:
            logger.error(f"Failed to upload facts. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
