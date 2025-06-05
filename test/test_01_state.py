from aot_cast.onto import (
    AgentState,
    RDFGraph,
    ONTOLOGY_VOID_ID,
)

from aot_cast.agent import select_ontology, chunk_text
from rdflib import URIRef, Literal
import pytest


def test_agent_state_json():
    state = AgentState()
    state.graph_facts = RDFGraph()
    state.graph_facts.add(
        (
            URIRef("http://example.com/subject"),
            URIRef("http://example.com/predicate"),
            Literal("object"),
        )
    )

    state_json = state.model_dump_json()

    loaded_state = AgentState.model_validate_json(state_json)

    assert isinstance(loaded_state.graph_facts, RDFGraph)


def test_chunks(agent_state_init: AgentState, apple_report: dict, tools):
    state = agent_state_init
    state.set_text(apple_report["text"])
    state = chunk_text(state, tools)
    assert len(state.chunks) == 10


@pytest.mark.order(after="test_agent_state_json")
def test_select_ontology(
    agent_state_init: AgentState,
    apple_report: dict,
    random_report: dict,
    tools,
    state_onto_selected_filename,
    state_onto_null_filename,
):
    state = agent_state_init
    state.set_text(apple_report["text"])
    state = select_ontology(state=state, tools=tools)
    assert "fsec" in state.current_ontology.iri

    state.serialize(state_onto_selected_filename)

    state.set_text(random_report["text"])
    state = select_ontology(state=state, tools=tools)
    assert state.current_ontology.short_name == ONTOLOGY_VOID_ID

    agent_state_init.serialize(state_onto_null_filename)
