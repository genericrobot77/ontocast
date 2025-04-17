import pathlib
import logging
from src.onto import Ontology
import abc
from rdflib import Graph
# from langchain.tools import Tool

logger = logging.getLogger(__name__)


# class TripleStoreManager(Tool):
class TripleStoreManager:
    def __init__(self, **kwargs):
        pass

    @abc.abstractmethod
    def fetch_ontologies(self):
        pass

    @abc.abstractmethod
    def serialize_triples():
        pass


class FilesystemTripleStoreManager(TripleStoreManager):
    def __init__(
        self, working_directory: pathlib.Path, ontology_path: pathlib.Path, **kwargs
    ):
        super().__init__(**kwargs)

        self.working_directory = working_directory
        self.ontology_path = ontology_path
        super

    def fetch_ontologies(self):
        if self.ontology_path is not None:
            for fname in self.ontology_path.glob("*.ttl"):
                try:
                    ontology = Ontology.from_file(fname)
                    self.ontologies.append(ontology)
                except Exception as e:
                    logging.error(f"Failed to load ontology {fname}: {str(e)}")

    def serialize_triples(self, g: Graph, fname):
        filename = self.working_directory / f"{fname}.ttl"
        g.serialize(format="turtle", file_path=filename)
