from src.onto import AgentState
from src.agent import select_ontology


# @pytest.mark.skip(reason="This test works")
def test_agent_state(agent_state: AgentState):
    assert len(agent_state.ontologies) == 1

    assert "court" in agent_state.ontologies[0].title
    assert "legal" in agent_state.ontologies[0].description


def test_agent_state_with_reports(
    agent_state: AgentState, apple_report: dict, legal_report: dict, random_report: dict
):
    AgentState.input_text = random_report["text"]
    agent_state = select_ontology(agent_state)
    assert agent_state.current_ontology_name is None

    AgentState.input_text = legal_report["text"]
    agent_state = select_ontology(agent_state)
    assert "fcaont#" in agent_state.current_ontology.uri

    AgentState.input_text = apple_report["text"]
    agent_state = select_ontology(agent_state)
    assert "fsec#" in agent_state.current_ontology.uri
