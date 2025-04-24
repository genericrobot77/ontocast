from src.onto import Ontology, RDFGraph, ONTOLOGY_VOID_ID, ONTOLOGY_VOID_IRI
from .onto import Tool
from pydantic import Field


class OntologyManager(Tool):
    ontologies: list[Ontology] = Field(default_factory=list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_ontology(self, short_name: str, ontology_addendum: Ontology):
        current_idx = next(
            i for i, o in enumerate(self.ontologies) if o.short_name == short_name
        )
        self.ontologies[current_idx] += ontology_addendum

    def get_ontology_names(self) -> list[str]:
        return [o.short_name for o in self.ontologies]

    def get_ontology(self, short_name: str) -> Ontology:
        if short_name in [o.short_name for o in self.ontologies]:
            current_idx = next(
                i for i, o in enumerate(self.ontologies) if o.short_name == short_name
            )
            return self.ontologies[current_idx]
        else:
            return Ontology(
                short_name=ONTOLOGY_VOID_ID,
                title="null title",
                description="null description",
                graph=RDFGraph(),
                iri=ONTOLOGY_VOID_IRI,
            )
