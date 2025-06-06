import pytest

from ontocast.agent import render_facts, sublimate_ontology, criticise_facts
from ontocast.onto import AgentState, Status


@pytest.mark.order(after="test_agent_text_to_ontology_null_critique_loop")
def test_agent_render_facts(
    state_onto_criticized: AgentState, apple_report: dict, tools, max_iter
):
    state = state_onto_criticized

    state.set_text(apple_report["text"])
    state = render_facts(state=state, tools=tools)

    state.status = Status.FAILED

    assert len(state.graph_facts) > 0
    state = sublimate_ontology(state=state, tools=tools)


@pytest.mark.order(after="test_agent_text_to_ontology_null_critique_loop")
def test_agent_text_to_facts_critique_loop(
    state_facts_criticized: AgentState, apple_report: dict, tools, max_iter
):
    state = state_facts_criticized
    state = criticise_facts(state=state, tools=tools)

    assert state.success_score > 0

    if state.status == Status.SUCCESS:
        state.serialize("test/data/agent_state.facts.critique.success.json")
    else:
        state.serialize("test/data/agent_state.facts.critique.loop.json")
    state.status = Status.SUCCESS
    state.clear_failure()
