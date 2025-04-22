import pytest
import os
from pathlib import Path
from src.onto import AgentState, RDFGraph, ToolType
from suthing import FileHandle
from src.tools import LLMTool, FilesystemTripleStoreManager, OntologyManager


# Set test environment variables
os.environ["CURRENT_DOMAIN"] = "https://test.growgraph.dev"
os.environ["CURRENT_NS_URI"] = "https://test.example.com/current-document#"


@pytest.fixture
def test_ontology():
    return RDFGraph._from_turtle_str("""
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix ex: <http://example.org/> .

    ex:TestOntology rdf:type owl:Ontology ;
        rdfs:label "Test Domain Ontology" ;
        rdfs:comment "An ontology for testing that covers basic concepts and relationships in a test domain. Used for validating ontology processing functionality." .
    """)


@pytest.fixture
def llm_tool():
    model_name = "gpt-4o-mini"
    temperature = 0.0
    llm_tool = LLMTool.create(model=model_name, temperature=temperature)
    return llm_tool


@pytest.fixture
def tsm_tool():
    ontology_path: Path = Path("data/ontologies")
    working_directory = Path("test/tmp")
    return FilesystemTripleStoreManager(
        working_directory=working_directory, ontology_path=ontology_path
    )


@pytest.fixture
def om_tool():
    return OntologyManager()


@pytest.fixture
def tools(llm_tool, tsm_tool, om_tool):
    tools = {
        ToolType.LLM: llm_tool,
        ToolType.TRIPLE_STORE: tsm_tool,
        ToolType.ONTOLOGY_MANAGER: om_tool,
    }
    return tools


@pytest.fixture
def max_iter():
    return 2


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
def agent_state_init(tools):
    try:
        return AgentState.load("test/data/agent_state.init.json")
    except (FileNotFoundError, Exception):
        state = AgentState(ontology_path="data/ontologies")
        return state


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
