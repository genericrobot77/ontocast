"""Ontology management tool for OntoCast.

This module provides functionality for managing multiple ontologies, including
loading, updating, and retrieving ontologies by name or IRI.
"""

from pydantic import Field

from ontocast.onto import NULL_ONTOLOGY, Ontology, RDFGraph

from .onto import Tool


class OntologyManager(Tool):
    """Manager for handling multiple ontologies.

    This class provides functionality for managing a collection of ontologies,
    including selection and retrieval operations.

    Attributes:
        ontologies: List of managed ontologies.
    """

    ontologies: list[Ontology] = Field(default_factory=list)

    def __init__(self, **kwargs):
        """Initialize the ontology manager.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)

    def update_ontology(self, ontology_id: str, ontology_addendum: RDFGraph):
        """Update an existing ontology with additional triples.

        Args:
            ontology_id: The short name of the ontology to update.
            ontology_addendum: The RDF graph containing additional triples to add.
        """
        current_idx = next(
            i for i, o in enumerate(self.ontologies) if o.ontology_id == ontology_id
        )
        self.ontologies[current_idx] += ontology_addendum

    def get_ontology_names(self) -> list[str]:
        """Get a list of all ontology short names.

        Returns:
            list[str]: List of ontology short names.
        """
        return [o.ontology_id for o in self.ontologies]

    def get_ontology(self, ontology_id: str) -> Ontology:
        """Get an ontology by its short name.

        Args:
            ontology_id: The short name of the ontology to retrieve.

        Returns:
            Ontology: The matching ontology if found, NULL_ONTOLOGY otherwise.
        """
        if ontology_id in [o.ontology_id for o in self.ontologies]:
            current_idx = next(
                i for i, o in enumerate(self.ontologies) if o.ontology_id == ontology_id
            )
            return self.ontologies[current_idx]
        else:
            return NULL_ONTOLOGY
