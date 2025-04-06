from src.onto import AgentState, RDFGraph
from src.agent import select_ontology
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


def test_agent_state_with_reports(
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
