import pytest

from ontocast.onto import Ontology, RDFGraph

pytestmark = pytest.mark.usefixtures("neo4j_triple_store_manager")


def test_neo4j_triple_store_roundtrip(neo4j_triple_store_manager, test_ontology):
    manager = neo4j_triple_store_manager
    ontology = Ontology(graph=test_ontology)
    # Store ontology
    manager.serialize_ontology(ontology)
    # Fetch ontologies
    onts = manager.fetch_ontologies()
    assert any(o.ontology_id == "ex_onto" for o in onts)
    # Store facts
    facts = RDFGraph()
    manager.serialize_facts(facts)
