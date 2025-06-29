import logging
import os
from typing import Optional

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

from ontocast.onto import Ontology, derive_ontology_id
from ontocast.tool.triple_manager.core import TripleStoreManager

logger = logging.getLogger(__name__)


class FusekiTripleStoreManager(TripleStoreManager):
    """Fuseki-based triple store manager."""

    def __init__(
        self,
        uri: Optional[str] = None,
        auth: Optional[str] = None,
        dataset: Optional[str] = None,
        **kwargs,
    ):
        # URI and auth can be passed or taken from environment
        self.uri = uri or os.getenv("FUSEKI_URI", "http://localhost:3030")
        auth_env = auth or os.getenv("FUSEKI_AUTH")
        if auth_env:
            if "/" in auth_env:
                user, password = auth_env.split("/", 1)
                self.auth = (user, password)
            else:
                raise ValueError("FUSEKI_AUTH must be in 'user/password' format")
        else:
            self.auth = None
        # Dataset can be part of the URI or passed separately
        self.dataset = dataset or self._parse_dataset_from_uri(self.uri)
        if self.dataset is None:
            raise ValueError("Dataset must be specified in FUSEKI_URI or as argument")
        # Base endpoint (strip dataset from uri if present)
        self.base_url = self.uri.rstrip("/").rsplit("/", 1)[0]
        super().__init__(**kwargs)

    def _parse_dataset_from_uri(self, uri: str) -> Optional[str]:
        # Expecting uri like http://localhost:3030/dataset
        parts = uri.rstrip("/").split("/")
        if len(parts) > 0:
            return parts[-1]
        return None

    def _get_dataset_url(self):
        return f"{self.base_url}/{self.dataset}"

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
        url = f"{self._get_dataset_url()}/data?graph={graph_uri}"
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
