import pathlib
import logging
from typing import Optional
from ontocast.onto import Ontology
import abc
from rdflib import Graph
from .onto import Tool

logger = logging.getLogger(__name__)


class TripleStoreManager(Tool):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @abc.abstractmethod
    def fetch_ontologies(self) -> list[Ontology]:
        return []

    @abc.abstractmethod
    def serialize_ontology(self, o: Ontology, **kwargs):
        pass

    @abc.abstractmethod
    def serialize_facts(self, g: Graph, **kwargs):
        pass


class FilesystemTripleStoreManager(TripleStoreManager):
    working_directory: pathlib.Path
    ontology_path: Optional[pathlib.Path]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def fetch_ontologies(self) -> list[Ontology]:
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
        fname = f"ontology_{o.short_name}_{o.version}"
        o.graph.serialize(
            format="turtle", destination=self.working_directory / f"{fname}.ttl"
        )

    def serialize_facts(self, g: Graph, **kwargs):
        # TODO change to chunk props
        fname = "current"
        filename = self.working_directory / f"{fname}.ttl"
        g.serialize(format="turtle", destination=filename)
