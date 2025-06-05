import pytest
from packaging.version import Version

from aot_cast.agent import render_onto_triples, criticise_ontology
from aot_cast.onto import AgentState, DEFAULT_DOMAIN, Status


@pytest.mark.order(after="test_select_ontology")
def test_agent_text_to_ontology_fresh(
    state_ontology_selected: AgentState, apple_report: dict, tools
):
    """here no relevant ontology is present, we are trying to create a new one"""
    state_ontology_selected.set_text(apple_report["text"])
    agent_state = render_onto_triples(state=state_ontology_selected, tools=tools)

    assert agent_state.ontology_addendum.iri is not None
    assert agent_state.ontology_addendum.title is not None
    assert agent_state.ontology_addendum.short_name is not None
    assert agent_state.ontology_addendum.description is not None
    assert agent_state.ontology_addendum.iri.startswith(DEFAULT_DOMAIN)
    assert len(agent_state.ontology_addendum.graph) > 0
    assert Version(agent_state.ontology_addendum.version) >= Version("0.0.0")
    agent_state.serialize("test/data/agent_state.onto.fresh.json")


@pytest.mark.order(after="test_select_ontology")
def test_agent_render_ontology(
    state_ontology_selected: AgentState, apple_report: dict, tools, max_iter
):
    state = state_ontology_selected
    state.set_text(apple_report["text"])
    state.status = Status.FAILED

    state = render_onto_triples(state=state, tools=tools)
    assert state.ontology_addendum.iri is not None
    assert state.ontology_addendum.iri.startswith(DEFAULT_DOMAIN)
    assert len(state.ontology_addendum.graph) > 0
    state.serialize("test/data/state_onto_rendered.json")


@pytest.mark.order(after="test_agent_render_ontology")
def test_state_onto_criticized(
    state_ontology_rendered: AgentState, apple_report: dict, tools, max_iter
):
    state = criticise_ontology(state_ontology_rendered, tools=tools)
    print(
        len(state.current_ontology.graph),
        len(state.ontology_addendum.graph),
    )
    print(f"current version: {Version(state.ontology_addendum.version)}")
    print(f"success score: {state.success_score}")
    print(state.failure_reason)
    assert state.status == Status.FAILED
    state.clear_failure()
    state.serialize("test/data/state_onto_criticized.json")
