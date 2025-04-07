import pytest
from src.onto import AgentState
import pathlib
from suthing import FileHandle


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


# @pytest.fixture
# def criminal_ontology() -> Ontology:
#     return Ontology.from_file(pathlib.Path("data/ontologies/criminal.ttl"))


# @pytest.fixture
# def security_ontology() -> Ontology:
#     return Ontology.from_file(pathlib.Path("data/ontologies/fin-securities.ttl"))


@pytest.fixture
def apple_report():
    r = FileHandle.load(pathlib.Path("data/json/fin.10Q.apple.json"))
    return {"text": r["text"][:8870]}


@pytest.fixture
def random_report():
    return FileHandle.load(pathlib.Path("data/json/random.json"))


@pytest.fixture
def legal_report():
    return FileHandle.load(
        pathlib.Path("data/json/legal.pourvoi_n°22-86.022_10_01_2023.json")
    )


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
def agent_state_project_triples():
    return AgentState.load("test/data/agent_state.project_triples.json")
