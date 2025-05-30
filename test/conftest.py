import pytest
import os
from aot_cast.tb import init_toolbox
from pathlib import Path
from aot_cast.onto import AgentState, RDFGraph, DEFAULT_DOMAIN
from suthing import FileHandle
from aot_cast.tool import (
    LLMTool,
    FilesystemTripleStoreManager,
    OntologyManager,
    ToolBox,
)


@pytest.fixture(scope="session", autouse=True)
def set_env_vars():
    os.environ["CURRENT_DOMAIN"] = DEFAULT_DOMAIN


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
def ontology_path():
    return Path("data/ontologies")


@pytest.fixture
def working_directory():
    return Path("test/tmp")


@pytest.fixture
def model_name():
    return "gpt-4o-mini"


@pytest.fixture
def temperature():
    return 0.0


@pytest.fixture
def llm_tool(model_name, temperature):
    llm_tool = LLMTool.create(model=model_name, temperature=temperature)
    return llm_tool


@pytest.fixture
def tsm_tool(ontology_path, working_directory):
    return FilesystemTripleStoreManager(
        working_directory=working_directory, ontology_path=ontology_path
    )


@pytest.fixture
def om_tool_fname():
    return "test/data/om_tool.json"


@pytest.fixture
def state_onto_selected_fname():
    return "test/data/agent_state.select_ontology.json"


@pytest.fixture
def state_onto_null_fname():
    return "test/data/agent_state.select_ontology.null.json"


@pytest.fixture
def om_tool(om_tool_fname):
    try:
        return OntologyManager.load(om_tool_fname)
    except (FileNotFoundError, Exception):
        return OntologyManager()


@pytest.fixture
def tools(ontology_path, working_directory, model_name, temperature) -> ToolBox:
    tools: ToolBox = ToolBox(
        working_directory=working_directory,
        ontology_directory=ontology_path,
        model_name=model_name,
        temperature=temperature,
    )
    init_toolbox(tools)
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
def agent_state_init():
    state = AgentState()
    return state


@pytest.fixture
def agent_state_select_ontology(state_onto_selected_fname):
    return AgentState.load(state_onto_selected_fname)


@pytest.fixture
def agent_state_select_ontology_null(state_onto_null_fname):
    return AgentState.load(state_onto_null_fname)


@pytest.fixture
def agent_state_onto_fresh():
    return AgentState.load("test/data/agent_state.onto.fresh.json")


@pytest.fixture
def agent_state_onto_critique():
    return AgentState.load("test/data/agent_state.onto.critique.json")


@pytest.fixture
def agent_state_onto_critique_success():
    return AgentState.load("test/data/agent_state.onto.null.critique.success.json")
