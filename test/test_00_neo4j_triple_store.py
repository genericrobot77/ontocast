from test.conftest import (
    triple_store_roundtrip,
    triple_store_serialize_empty_facts,
    triple_store_serialize_facts,
)


def test_neo4j_triple_store_roundtrip(neo4j_triple_store_manager, test_ontology):
    triple_store_roundtrip(neo4j_triple_store_manager, test_ontology)


def test_neo4j_serialize_facts(neo4j_triple_store_manager):
    triple_store_serialize_facts(neo4j_triple_store_manager)


def test_neo4j_serialize_empty_facts(neo4j_triple_store_manager):
    triple_store_serialize_empty_facts(neo4j_triple_store_manager)
