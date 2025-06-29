from test.conftest import (
    triple_store_roundtrip,
    triple_store_serialize_empty_facts,
    triple_store_serialize_facts,
)


def test_fuseki_triple_store_roundtrip(fuseki_triple_store_manager, test_ontology):
    triple_store_roundtrip(fuseki_triple_store_manager, test_ontology)


def test_fuseki_serialize_facts(fuseki_triple_store_manager):
    triple_store_serialize_facts(fuseki_triple_store_manager)


def test_fuseki_serialize_empty_facts(fuseki_triple_store_manager):
    triple_store_serialize_empty_facts(fuseki_triple_store_manager)
