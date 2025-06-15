"""Triple store management tools for OntoCast.

This module provides functionality for managing RDF triple stores, including
abstract interfaces and filesystem-based implementations.
"""

import abc
import logging
import pathlib
from typing import Optional

from rdflib import Graph

from ontocast.onto import Ontology

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
        fname = f"ontology_{o.short_name}_{o.version}"
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
