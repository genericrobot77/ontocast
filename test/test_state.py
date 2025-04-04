from src.onto import AgentState


def test_agent_state():
    state = AgentState(ontology_path="data/ontologies")
    assert len(state.ontologies) == 1
    assert "court" in state.ontologies[0].title
    assert "legal" in state.ontologies[0].description
