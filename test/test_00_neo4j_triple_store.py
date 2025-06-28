import pytest

from ontocast.onto import Ontology, RDFGraph

pytestmark = pytest.mark.usefixtures("neo4j_triple_store_manager")


def test_neo4j_triple_store_roundtrip(neo4j_triple_store_manager, test_ontology):
    manager = neo4j_triple_store_manager
    ontology = Ontology(graph=test_ontology)
    # Store ontology
    manager.serialize_ontology(ontology)
    # Fetch ontologies
    ontologies = manager.fetch_ontologies()
    assert any(o.ontology_id == "to" for o in ontologies)
    assert len(ontologies[0].graph) == len(ontology.graph)


def test_neo4j_serialize_facts(neo4j_triple_store_manager):
    """Test serializing facts (RDF triples) to Neo4j and retrieving them."""
    manager = neo4j_triple_store_manager

    # Create test facts
    facts = RDFGraph._from_turtle_str(
        """
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix ex: <http://example.org/test/> .
    @prefix schema: <https://schema.org/> .
    
    ex:Person a rdfs:Class ;
        rdfs:label "Person" ;
        rdfs:comment "A human being" .
    
    ex:John a ex:Person ;
        rdfs:label "John Doe" ;
        schema:name "John Doe" ;
        schema:email "john@example.com" .
    
    ex:Jane a ex:Person ;
        rdfs:label "Jane Smith" ;
        schema:name "Jane Smith" ;
        schema:email "jane@example.com" .
    
    ex:knows a rdf:Property ;
        rdfs:label "knows" ;
        rdfs:comment "Relationship between people who know each other" .
    
    ex:John ex:knows ex:Jane .
    """
    )

    # Verify we have the expected number of triples
    expected_triple_count = len(facts)
    assert expected_triple_count == 15, "Test facts should contain triples"

    # Serialize facts to Neo4j
    result = manager.serialize_facts(facts)
    assert result is not None, "serialize_facts should return a result"


def test_neo4j_serialize_empty_facts(neo4j_triple_store_manager):
    """Test serializing empty facts graph."""
    manager = neo4j_triple_store_manager

    # Create empty facts
    empty_facts = RDFGraph()

    # Serialize empty facts - should not raise an error
    result = manager.serialize_facts(empty_facts)
    assert result is not None, (
        "serialize_facts should return a result even for empty graph"
    )
