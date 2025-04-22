import pathlib
import logging
from src.onto import Ontology
import abc
from rdflib import Graph
from .onto import Tool

logger = logging.getLogger(__name__)


class TripleStoreManager(Tool):
    def __init__(self, **kwargs):
        pass

    @abc.abstractmethod
    def fetch_ontologies(self) -> list[Ontology]:
        return []

    @abc.abstractmethod
    def serialize_triples(self, g: Graph, **kwargs):
        pass


class FilesystemTripleStoreManager(TripleStoreManager):
    def __init__(
        self, working_directory: pathlib.Path, ontology_path: pathlib.Path, **kwargs
    ):
        super().__init__(**kwargs)

        self.working_directory = working_directory
        self.ontology_path = ontology_path

    def fetch_ontologies(self) -> list[Ontology]:
        ontologies = []
        for fname in self.ontology_path.glob("*.ttl"):
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
