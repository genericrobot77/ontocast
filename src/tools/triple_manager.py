import pathlib
import logging
from typing import Optional
from src.onto import Ontology
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
    def serialize_triples(self, g: Graph, **kwargs):
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

    def serialize_triples(self, g: Graph, **kwargs):
        fname = kwargs.get("fname")
        filename = self.working_directory / f"{fname}.ttl"
        g.serialize(format="turtle", file_path=filename)
