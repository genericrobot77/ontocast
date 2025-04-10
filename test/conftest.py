import pytest
import os
from pathlib import Path
from src.onto import AgentState
from suthing import FileHandle

# Set test environment variables
os.environ["CURRENT_DOMAIN"] = "https://test.growgraph.dev"
os.environ["CURRENT_NS_URI"] = "https://test.example.com/current-document#"


@pytest.fixture
def test_ontology():
    return """
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix ex: <http://example.org/> .

    ex:TestOntology rdf:type owl:Ontology ;
        rdfs:label "Test Domain Ontology" ;
        rdfs:comment "An ontology for testing that covers basic concepts and relationships in a test domain. Used for validating ontology processing functionality." .
    """


@pytest.fixture
def apple_report():
    r = FileHandle.load(Path("data/json/fin.10Q.apple.json"))
    return {"text": r["text"][:8870]}


@pytest.fixture
def random_report():
    return FileHandle.load(Path("data/json/random.json"))


@pytest.fixture
def legal_report():
    return FileHandle.load(Path("data/json/legal.pourvoi_n°22-86.022_10_01_2023.json"))


@pytest.fixture
def agent_state_init():
    try:
        return AgentState.load("test/data/agent_state.init.json")
    except (FileNotFoundError, Exception):
        return AgentState(ontology_path="data/ontologies")


@pytest.fixture
def agent_state_select_ontology():
    return AgentState.load("test/data/agent_state.select_ontology.json")


@pytest.fixture
def agent_state_onto_fresh():
    return AgentState.load("test/data/agent_state.onto.fresh.json")


@pytest.fixture
def agent_state_onto_critique():
    return AgentState.load("test/data/agent_state.onto.critique.json")


@pytest.fixture
def agent_state_onto_critique_success():
    return AgentState.load("test/data/agent_state.onto.critique.success.json")


# @pytest.fixture
# def agent_state_project_triples():
#     return AgentState.load("test/data/agent_state.project_triples.json")


# @pytest.fixture
# def agent_state_sublimate_ontology():
#     return AgentState.load("test/data/agent_state.sublimate_ontology.json")


# @pytest.fixture
# def agent_state_criticise_ontology_update_success():
#     return AgentState.load(
#         "test/data/agent_state.criticise_ontology_update.success.json"
#     )


# @pytest.fixture
# def agent_state_criticise_ontology_update_failed():
#     return AgentState.load(
#         "test/data/agent_state.criticise_ontology_update.failed.json"
#     )


# @pytest.fixture
# def agent_state_update_ontology():
#     return AgentState.load("test/data/agent_state.update_ontology.json")
