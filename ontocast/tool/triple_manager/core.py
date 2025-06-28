import abc

from rdflib import Graph

from ontocast.onto import Ontology
from ontocast.tool import Tool


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
