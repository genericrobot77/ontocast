import pytest
from aot_cast.onto import Chunk
from aot_cast.agent.aggregate import ChunkRDFGraphAggregator
from aot_cast.agent.validate import (
    validate_and_connect_chunk,
    RDFGraphConnectivityValidator,
)
from rdflib import URIRef, Literal
from rdflib.namespace import RDFS
from aot_cast.onto import RDFGraph


def create_sample_chunk_graph(current_domain, chunk_id: str) -> Chunk:
    g = RDFGraph()
    doc_iri = f"{current_domain}/doc/123"
    c = Chunk(graph=g, doc_iri=doc_iri, text="", hid=chunk_id)

    person1 = URIRef(c.namespace + "person1")
    person2 = URIRef(c.namespace + "person2")

    g.add((person1, RDFS.label, Literal("John Doe")))
    g.add((person1, URIRef(c.namespace + "knows"), person2))
    g.add((person2, RDFS.label, Literal("Jane Smith")))
    c.graph = g
    return c


@pytest.fixture
def doc_id():
    return "123"


@pytest.fixture
def sample_chunks(current_domain):
    ids = ["abc123", "def456"]
    sample_chunks = {
        i: create_sample_chunk_graph(chunk_id=i, current_domain=current_domain)
        for i in ids
    }
    return sample_chunks


@pytest.fixture
def connected_chunks(sample_chunks, current_domain):
    connected_chunks = {}
    for _, chunk in sample_chunks.items():
        new_chunk = validate_and_connect_chunk(
            chunk, auto_connect=True, current_domain=current_domain
        )
        connected_chunks[new_chunk.hid] = new_chunk
    return connected_chunks


def test_validation(sample_chunks, current_domain):
    gs = []
    for _, chunk in sample_chunks.items():
        new_chunk = validate_and_connect_chunk(
            chunk, auto_connect=True, current_domain=current_domain
        )
        gs += [new_chunk]

    assert [len(x.graph) for x in gs] == [3, 3]


def test_aggregation(doc_id, connected_chunks, current_domain):
    # Aggregate graphs (now using connected versions)
    aggregator = ChunkRDFGraphAggregator(doc_iri=f"{current_domain}/{doc_id}")
    aggregated_graph = aggregator.aggregate_graphs(chunks=connected_chunks)

    # Validate aggregated graph connectivity
    connectivity_result = RDFGraphConnectivityValidator(
        aggregated_graph, current_domain=current_domain
    ).validate_connectivity()
    assert len(aggregated_graph) == 11
    assert connectivity_result["num_components"] == 1
