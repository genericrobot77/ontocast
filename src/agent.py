import logging

from langgraph.graph import END, StateGraph, START
import re

from src.onto import AgentState, OntologySelector, TriplesProjection, RDFGraph
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


def project_text_to_triples_with_ontology(state: AgentState) -> AgentState:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    parser = PydanticOutputParser(pydantic_object=TriplesProjection)

    if state.current_ontology_name is None:
        ontology_uri = current_ontology_uri
    else:
        ontology_uri = state.current_ontology.uri
        ontology_str = state.current_ontology.graph.serialize(format="turtle")

    ontology_instruction = (
        f"""
        Be guided by the following ontology <{state.current_ontology.uri}>
            
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
        - entities representing facts must use the namespace `@prefix co: <{ontology_uri}> .` 
        - entities representing abstract concepts must use the namespace `@prefix cd: <{current_ns_uri}> .` 
        - all entities from `cd:` namespace must IMPERATIVELY linked to entities from basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
        - all facts must form a connected graph with respect to namespace `cd`.
        - all facts and entities representing numeric values, dates etc should not be kept in literal strings: expand them into triple and use xsd:integer, xsd:decimal, xsd:float, xsd:date for dates, ISO for currencies, etc, assign correct units and define correct relations.
        - pay attention to constraints and axioms of the ontology. Feel free to add new constraints and axioms if needed.
        - make semantic representation of facts and entities as atomic (!!!)  as possible.
        - data from tables should be represented as triples.

        {failure_instruction}

        Here is the document:
        {text}

        {failure_instruction}

        {format_instructions}
    """

    prompt = PromptTemplate(
        template=template_prompt,
        input_variables=[
            "ontology_uri",
            "current_ns_uri",
            "text",
            "ontology_addendum",
            "ontology_instruction",
            "failure_instruction",
            "format_instructions",
        ],
    )

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            if state.failure_reason is not None:
                failure_instruction = f"""
                The previous attempt to generate triples failed because of the following reason:
                {state.failure_reason}

                Please fix the errors and do your best to generate triples again.
                """
            else:
                failure_instruction = ""
            response = llm(
                prompt.format_prompt(
                    ontology_uri=ontology_uri,
                    current_ns_uri=current_ns_uri,
                    text=state.input_text,
                    ontology_addendum=ontology_addendum,
                    ontology_instruction=ontology_instruction,
                    failure_instruction=failure_instruction,
                    format_instructions=parser.get_format_instructions(),
                )
            )

            proj = parser.parse(response.content)
            state.current_graph = proj.semantic_graph
            state.failure_reason = None
            return state

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            state.failure_reason = str(e)
            last_error = e
            if attempt == max_retries - 1:  # Last attempt
                logger.error("All retry attempts failed")
                state.current_graph = RDFGraph()
                state.failure_reason = (
                    f"All attempts failed. Last error: {str(last_error)}"
                )
                return state
            continue

    return state


def select_ontology(state: AgentState) -> AgentState:
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Define the output parser
    parser = PydanticOutputParser(pydantic_object=OntologySelector)

    ontologies_desc = "\n\n".join(
        [
            f"Ontology name: {o.short_name}\n"
            f"Description: {o.description}\n"
            f"Ontology URI: {o.uri}\n"
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


def sublimate_ontology_route(state: AgentState) -> str:
    """Decide next step after sublimation"""
    # Logic to decide route based on state
    if state.knowledge_graph and len(state.knowledge_graph) > 0:
        return "success"
    else:
        return "failure"


def project_text_to_triples_route(state: AgentState) -> str:
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
    workflow.add_node("Text to Triples", project_text_to_triples_with_ontology)
    workflow.add_node("Sublimate Ontology", sublimate_ontology)
    workflow.add_node("Update Existing Ontology", update_ontology)
    workflow.add_node("Criticise KG", criticise_kg)
    workflow.add_node("Update KG", update_kg)

    # Standard edges
    workflow.add_edge(START, "Select Ontology")
    workflow.add_edge("Select Ontology", "Text to Triples")
    workflow.add_edge("Update KG", END)

    # Conditional edges with clear routing functions

    workflow.add_conditional_edges(
        "Text to Triples",
        project_text_to_triples_route,
        {"success": "Sublimate Ontology", "failure": END},
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
