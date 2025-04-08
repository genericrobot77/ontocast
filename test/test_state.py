from src.onto import AgentState, RDFGraph, Status
from src.agent import (
    select_ontology,
    project_text_to_triples_with_ontology,
    _sublimate_ontology,
    sublimate_ontology,
    criticise_ontology_update,
    update_ontology,
)
from rdflib import URIRef, Literal


def test_agent_state(agent_state_init: AgentState):
    assert len(agent_state_init.ontologies) == 2

    assert "court" in agent_state_init.ontologies[0].title.lower()
    assert "legal" in agent_state_init.ontologies[0].description.lower()
    agent_state_init.serialize("test/data/agent_state.init.json")


def test_agent_state_json():
    state = AgentState()
    state.knowledge_graph.add(
        (
            URIRef("http://example.com/subject"),
            URIRef("http://example.com/predicate"),
            Literal("object"),
        )
    )

    state_json = state.model_dump_json()

    loaded_state = AgentState.model_validate_json(state_json)

    assert isinstance(loaded_state.knowledge_graph, RDFGraph)


def test_select_ontology(
    agent_state_init: AgentState,
    apple_report: dict,
    legal_report: dict,
    random_report: dict,
):
    agent_state_init.input_text = random_report["text"]
    agent_state_init = select_ontology(agent_state_init)
    assert agent_state_init.current_ontology_name is None

    agent_state_init.input_text = legal_report["text"]
    agent_state = select_ontology(agent_state_init)
    assert "fcaont#" in agent_state.current_ontology.uri

    agent_state_init.input_text = apple_report["text"]
    agent_state = select_ontology(agent_state_init)
    assert "fsec#" in agent_state.current_ontology.uri

    agent_state_init.serialize("test/data/agent_state.select_ontology.json")


def test_agent_text_to_triples(
    agent_state_select_ontology: AgentState,
    apple_report: dict,
):
    agent_state_select_ontology.input_text = apple_report["text"]
    agent_state = project_text_to_triples_with_ontology(agent_state_select_ontology)
    assert "fsec#" in agent_state.current_ontology.uri
    assert len(agent_state.current_graph) > 0

    agent_state.serialize("test/data/agent_state.project_triples.json")


def test_agent_state_sublimate_ontology(
    agent_state_project_triples: AgentState,
):
    graph_onto_addendum, graph_facts = _sublimate_ontology(agent_state_project_triples)
    assert len(agent_state_project_triples.current_graph) == len(graph_facts) + len(
        graph_onto_addendum
    )


def test_agent_state_sublimate_ontology_aux(
    agent_state_project_triples: AgentState,
):
    state = sublimate_ontology(agent_state_project_triples)
    assert state.ontology_modified is not None
    assert len(state.graph_facts) > 0
    assert len(state.ontology_addendum) > 0
    assert state.status == Status.SUCCESS
    state.serialize("test/data/agent_state.sublimate_ontology.json")


def test_agent_state_criticise_ontology_update(
    agent_state_sublimate_ontology: AgentState,
):
    state = criticise_ontology_update(agent_state_sublimate_ontology)
    if state.status == Status.SUCCESS:
        state.serialize("test/data/agent_state.criticise_ontology_update.success.json")
    else:
        state.serialize("test/data/agent_state.criticise_ontology_update.failed.json")
        assert state.failure_reason is not None


def test_agent_state_update_ontology(
    agent_state_criticise_ontology_update_success: AgentState,
):
    state = update_ontology(agent_state_criticise_ontology_update_success)
    state.serialize("test/data/agent_state.update_ontology.json")
