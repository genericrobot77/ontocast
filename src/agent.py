import logging

from langgraph.graph import END, StateGraph, START
import rdflib
import re

from src.util import call_openai_api
from src.onto import AgentState

logger = logging.getLogger(__name__)


def extract_struct(text, key):
    # Pattern to match text between ```key and ```
    pattern = rf"```{key}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


# Define state structure
def project_triples(state: AgentState) -> str:
    prompt = """
        Process this document.
        There are two independent tasks: task A and task B.
        Generate semantic triples in turtle (ttl) format from the text below.
                
        Follow the instructions:
        
        - mark extracted semantic triples as ```ttl ```.
        - use commonly known ontologies (RDFS, OWL, schema etc) to place encountered abstract entities/properties and facts within a broader ontology.
        - entities representing facts must use the namespace `@prefix cd: <https://growgraph.dev/current#> .` 
        - all entities from `cd:` namespace must IMPERATIVELY linked to entities from basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
        - all facts must form a connected graph with respect to namespace `cd`.
        - make semantic representation as atomic as possible.
    """

    response = call_openai_api(prompt)

    return response


def format_output(response_raw: str) -> dict:
    """Format final output with knowledge graph and ontology status."""

    extracted_ttl = extract_struct(response_raw, "ttl")
    g = rdflib.Graph()
    try:
        _ = g.parse(data=extracted_ttl, format="turtle")
    except Exception as e:
        logger.error(f"{e}")

    return g


def decide_ontology(state: AgentState) -> AgentState:
    ontologies_desc = "\n\n".join(
        [
            f"Ontology name: {o.title} \n Description:{o.description}"
            for o in state.ontologies
        ]
    )

    prompt = f"""
        You are a helpful assistant that decides which ontology to use for a given document.
        You are given a list of ontologies and a document.
        You need to decide which ontology to use for the document.
        You need to return the name of the ontology.
        In case no ontology is suitable, return "none".
        Here is the list of ontologies:
        {ontologies_desc}
        Here is the document:
        {state.input_text}
    """

    response = call_openai_api(prompt)
    if response == "none":
        state.current_ontology_name = None
    elif response in [o.title for o in state.ontologies]:
        state.current_ontology_name = response
    else:
        raise ValueError(f"Invalid ontology name: {response}")
    return state


# Define conditional routing functions (separate from state modifiers)
def sublimate_ontology_route(state: AgentState) -> str:
    """Decide next step after sublimation"""
    # Logic to decide route based on state
    if state.knowledge_graph and len(state.knowledge_graph) > 0:
        return "success"
    else:
        return "failure"


def update_ontology_route(state: AgentState) -> str:
    """Decide next step after ontology update"""
    # Logic to decide route
    if state.ontology_modified:
        return "success"
    else:
        return "failure"


def criticise_kg_route(state: AgentState) -> str:
    """Decide next step after KG criticism"""
    # Logic to decide route
    # Placeholder for actual logic
    return "success"


# Define state modifying functions
def sublimate_ontology(state: AgentState) -> AgentState:
    """Extract ontology concepts from the knowledge graph"""
    # Actual implementation to modify state
    # ...
    return state


def update_ontology(state: AgentState) -> AgentState:
    """Update the ontology with the new facts"""
    # Actual implementation to modify state
    # ...
    state.ontology_modified = True
    return state


def criticise_kg(state: AgentState) -> AgentState:
    """Criticise the knowledge graph"""
    # Actual implementation to modify state
    # ...
    return state


def update_kg(state: AgentState) -> AgentState:
    """Update the knowledge graph with the new facts"""
    # Actual implementation to modify state
    # ...
    return state


# Define the workflow graph
def create_agent_graph():
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)
    # Add all nodes first
    workflow.add_node("decide_ontology", decide_ontology)
    workflow.add_node("project_triples", project_triples)
    workflow.add_node("sublimate_ontology", sublimate_ontology)
    workflow.add_node("update_ontology", update_ontology)
    workflow.add_node("criticise_kg", criticise_kg)
    workflow.add_node("update_kg", update_kg)

    # Standard edges
    workflow.add_edge(START, "decide_ontology")
    workflow.add_edge("decide_ontology", "project_triples")
    workflow.add_edge("project_triples", "sublimate_ontology")
    workflow.add_edge("update_kg", END)

    # Conditional edges with clear routing functions
    workflow.add_conditional_edges(
        "sublimate_ontology",
        sublimate_ontology_route,
        {"success": "update_ontology", "failure": "project_triples"},
    )

    workflow.add_conditional_edges(
        "update_ontology",
        update_ontology_route,
        {"success": "criticise_kg", "failure": "project_triples"},
    )

    workflow.add_conditional_edges(
        "criticise_kg",
        criticise_kg_route,
        {"success": "update_kg", "failure": "project_triples"},
    )

    return workflow.compile()
