import logging

from langgraph.graph import END, StateGraph, START
import rdflib
import re

from src.onto import AgentState, OntologySelector
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

current_ontology_uri = "https://example.com/current-ontology#"
current_ns_uri = "https://example.com/current-document#"


def extract_struct(text, key):
    # Pattern to match text between ```key and ```
    pattern = rf"```{key}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def project_triples(state: AgentState) -> str:
    if state.current_ontology_name is None:
        uri = current_ontology_uri
    else:
        uri = state.current_ontology.uri
        ontology_str = state.current_ontology.graph.serialize(format="turtle").decode(
            "utf-8"
        )

    ontology_instruction = (
        f"""
        Here is the ontology ({state.current_ontology.uri}):
            
        ```ttl
        {ontology_str}
        ```
    """
        if state.current_ontology_name is not None
        else ""
    )

    ontology_addendum = (
        "and the provided ontology {uri}, "
        if state.current_ontology_name is not None
        else ""
    )

    template_prompt = """
        Generate semantic triples in turtle (ttl) format from the text below.

        {ontology_instruction}
                
        Follow the instructions:
        
        - mark the block of extracted semantic triples as ```ttl ```.
        - use commonly known ontologies (RDFS, OWL, schema etc) {ontology_addendum}to place encountered abstract entities/properties and facts within a broader ontology.
        - entities representing facts must use the namespace `@prefix co: <{uri}> .` 
        - entities representing abstract concepts must use the namespace `@prefix cd: {current_ns_uri} .` 
        - all entities from `cd:` namespace must IMPERATIVELY linked to entities from basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
        - all facts must form a connected graph with respect to namespace `cd`.
        - pay attention to typing facts, such as using xsd:date for dates, xsd:integer for numbers, ISO for currencies, etc.
        - pay attention to constraints and axioms of the ontology. Feel free to add new constraints and axioms if needed.
        - make semantic representation as atomic as possible.


        Here is the document:
        {state.input_text}
    """

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

    prompt = PromptTemplate(
        template=template_prompt,
        input_variables=["ontology_uri", "text", "ontology_str"],
    )

    response = llm(
        prompt.format_prompt(
            ontology_uri=uri,
            text=state.input_text,
            ontology_addendum=ontology_addendum,
            current_ns_uri=current_ns_uri,
            ontology_instruction=ontology_instruction,
        )
    )

    return response.content


def validate_ttl(response_raw: str) -> dict:
    """Format final output with knowledge graph and ontology status."""

    extracted_ttl = extract_struct(response_raw, "ttl")
    g = rdflib.Graph()
    try:
        _ = g.parse(data=extracted_ttl, format="turtle")
    except Exception as e:
        logger.error(f"{e}")

    return g


def select_ontology(state: AgentState) -> AgentState:
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Define the output parser
    parser = PydanticOutputParser(pydantic_object=OntologySelector)

    ontologies_desc = "\n\n".join(
        [
            f"Ontology name: {o.short_name} \n Description:{o.description}"
            for o in state.ontologies
        ]
    )
    excerpt = state.input_text[:1000] + "..."

    prompt = """
        You are a helpful assistant that decides which ontology to use for a given document.
        You are given a list of ontologies and a document.
        You need to decide which ontology can be used for the document to create a semantic graph.
        Here is the list of ontologies:
        {ontologies_desc}
        
        Here is an excerpt from the document:
        {excerpt}

        {format_instructions}
    """

    # Create the prompt template with format instructions
    prompt = PromptTemplate(
        template=prompt,
        input_variables=["excerpt", "ontologies_desc", "format_instructions"],
    )

    response = llm(
        prompt.format_prompt(
            excerpt=excerpt,
            ontologies_desc=ontologies_desc,
            format_instructions=parser.get_format_instructions(),
        )
    )
    selector = parser.parse(response.content)

    if selector.short_name in state.ontology_names:
        state.current_ontology_name = selector.short_name
    return state


# Define conditional routing functions (separate from state modifiers)
def sublimate_ontology_route(state: AgentState) -> str:
    """Decide next step after sublimation"""
    # Logic to decide route based on state
    if state.knowledge_graph and len(state.knowledge_graph) > 0:
        return "success"
    else:
        return "failure"


def validate_ttl_route(state: AgentState) -> str:
    """Decide next step after ttl validation"""
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
    workflow.add_node("Select Ontology", select_ontology)
    workflow.add_node("Text to Triples", project_triples)
    workflow.add_node("Validate Triples", validate_ttl)
    workflow.add_node("Sublimate Ontology", sublimate_ontology)
    workflow.add_node("Update Existing Ontology", update_ontology)
    workflow.add_node("Criticise KG", criticise_kg)
    workflow.add_node("Update KG", update_kg)

    # Standard edges
    workflow.add_edge(START, "Select Ontology")
    workflow.add_edge("Select Ontology", "Text to Triples")
    workflow.add_edge("Text to Triples", "Validate Triples")
    workflow.add_edge("Update KG", END)

    # Conditional edges with clear routing functions

    workflow.add_conditional_edges(
        "Validate Triples",
        validate_ttl_route,
        {"success": "Sublimate Ontology", "failure": "Text to Triples"},
    )

    workflow.add_conditional_edges(
        "Sublimate Ontology",
        sublimate_ontology_route,
        {"success": "Update Existing Ontology", "failure": "Text to Triples"},
    )

    workflow.add_conditional_edges(
        "Update Existing Ontology",
        update_ontology_route,
        {"success": "Criticise KG", "failure": "Text to Triples"},
    )

    workflow.add_conditional_edges(
        "Criticise KG",
        criticise_kg_route,
        {"success": "Update KG", "failure": "Text to Triples"},
    )

    return workflow.compile()
