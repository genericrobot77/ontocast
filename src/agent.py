from rdflib import Namespace
import logging

from langgraph.graph import END, StateGraph, START
import re

from src.onto import (
    AgentState,
    OntologySelector,
    TriplesProjection,
    RDFGraph,
    Status,
    OntologyUpdateCritique,
    KGUpdateCritique,
)
from langchain.prompts import PromptTemplate

from src.tools import LLMTool

logger = logging.getLogger(__name__)

current_ontology_uri = "https://example.com/current-ontology#"
current_ns_uri = "https://example.com/current-document#"


# Create a global instance of the LLM tool
llm_tool = LLMTool()


def extract_struct(text, key):
    # Pattern to match text between ```key and ```
    pattern = rf"```{key}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def project_text_to_triples_with_ontology(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(TriplesProjection)

    if state.current_ontology_name is None:
        ontology_uri = current_ontology_uri
    else:
        ontology_uri = state.current_ontology.uri
        ontology_str = state.current_ontology.graph.serialize(format="turtle")

    ontology_instruction = (
        f"""
        Use the following ontology <{state.current_ontology.uri}>:
            
        ```ttl
        {ontology_str}
        ```
    """
        if state.current_ontology_name is not None
        else ""
    )

    ontology_addendum = (
        f"and the provided ontology <{state.current_ontology.uri}>, "
        if state.current_ontology_name is not None
        else ""
    )

    template_prompt = """
        Generate semantic triples in turtle (ttl) format from the text below.

        {ontology_instruction}
                
        Follow the instructions:
        
        - mark the block of extracted semantic triples as ```ttl ```
        - you can infer two types of entities from the document: entities that are concrete and specific to the document (otherwise called facts) that must use the namespace `@prefix cd: <{current_ns_uri}> .` and entities that are more abstract that must be either mapped to the domain ontology <{ontology_uri}> and more basic ontologies or added properly to the ontology <{ontology_uri}>.
        - use commonly known ontologies (RDFS, OWL, schema etc) {ontology_addendum} to place (define) entities/classes/types and relationships between them that can be inferred from the document.
        - all new abstract entities or properties added in <{ontology_uri}> namespace must be linked to entities from either domain ontology <{ontology_uri}> or basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc 
        - all entities identified by <{current_ns_uri}> namespace (facts, less abstract entities) must be linked to entities from either domain ontology <{ontology_uri}> or basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc 
        - all entities identified by <{current_ns_uri}> namespace must form a connected graph with respect to `cd:` namespace.
        - all facts representing numeric values, dates etc should not be kept in literal strings: expand them into triple and use xsd:integer, xsd:decimal, xsd:float, xsd:date for dates, ISO for currencies, etc, assign correct units and define correct relations.
        - pay attention to constraints and axioms of the ontology. Feel free to add new constraints and axioms if needed.
        - make semantic representation of facts and entities as atomic (!!!) as possible.
        - data from tables should be represented as triples.

        Here is the document:
        ```
        {text}
```
        
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

    try:
        if state.failure_reason is not None:
            failure_instruction = "The previous attempt to generate triples failed."
            if state.failure_stage is not None:
                failure_instruction += (
                    f"\n\nIt failed at the stage: {state.failure_stage}."
                )
            failure_instruction += f"\n\n{state.failure_reason}"
            failure_instruction += (
                "\n\nPlease fix the errors and do your best to generate triples again."
            )
        else:
            failure_instruction = ""

        response = llm_tool.llm(
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
        state.clear_failure()  # Clear any failure state on success
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure("Text to Triples", str(e))
        return state


def select_ontology(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(OntologySelector)

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

    response = llm_tool.llm(
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


def _sublimate_ontology(state: AgentState):
    query_ontology = f"""
    PREFIX cd: <{current_ns_uri}>
    
    SELECT ?s ?p ?o
    WHERE {{
    ?s ?p ?o .
    FILTER (
        !(
            STRSTARTS(STR(?s), STR(cd:)) ||
            STRSTARTS(STR(?p), STR(cd:)) ||
            (isIRI(?o) && STRSTARTS(STR(?o), STR(cd:)))
        )
    )
    }}
    """
    results = state.current_graph.query(query_ontology)

    graph_onto_addendum = RDFGraph()

    # Add filtered triples to the new graph
    for s, p, o in results:
        graph_onto_addendum.add((s, p, o))

    query_facts = f"""
        PREFIX cd: <{current_ns_uri}>

        SELECT ?s ?p ?o
        WHERE {{
        ?s ?p ?o .
        FILTER (
            STRSTARTS(STR(?s), STR(cd:)) ||
            STRSTARTS(STR(?p), STR(cd:)) ||
            (isIRI(?o) && STRSTARTS(STR(?o), STR(cd:)))
        )
        }}
    """

    graph_facts = RDFGraph()

    results = state.current_graph.query(query_facts)

    # Add filtered triples to the new graph
    for s, p, o in results:
        graph_facts.add((s, p, o))

    return graph_onto_addendum, graph_facts


def sublimate_ontology(state: AgentState) -> AgentState:
    """Separate ontology from facts"""
    try:
        graph_onto_addendum, graph_facts = _sublimate_ontology(state=state)

        ns_prefix_current_ontology = [
            p
            for p, ns in state.current_ontology.graph.namespaces()
            if str(ns) == state.current_ontology.uri
        ]

        graph_onto_addendum.bind(
            ns_prefix_current_ontology[0], Namespace(state.current_ontology.uri)
        )
        graph_facts.bind(
            ns_prefix_current_ontology[0], Namespace(state.current_ontology.uri)
        )
        state.ontology_addendum = graph_onto_addendum
        state.graph_facts = graph_facts
        state.clear_failure()
    except Exception as e:
        state.set_failure(
            "The produced semantic could not be validated or separated into ontology and facts (technical issue).",
            str(e),
        )

    return state


def criticise_ontology_update(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(OntologyUpdateCritique)

    prompt = """
        You are a helpful assistant that criticises the ontology update.
        You need to decide whether the ontology update is satisfactory.
        It is considered satisfactory if the ontology update captures all abstract classes and properties that present explicitly or implicitly in the document that are not already captured in the original ontology.

        Here is the original ontology:
        ```ttl
        {ontology_original}
        ```

        Here is the document from which the ontology was update was derived:
        {document}

                Here is the ontology update:
        ```ttl
        {ontology_update}
        ```

        {format_instructions}
    """

    prompt = PromptTemplate(
        template=prompt,
        input_variables=[
            "ontology_original",
            "ontology_update",
            "document",
            "format_instructions",
        ],
    )

    response = llm_tool.llm(
        prompt.format_prompt(
            ontology_original=state.current_ontology.graph.serialize(format="turtle"),
            ontology_update=state.ontology_addendum.serialize(format="turtle"),
            document=state.input_text,
            format_instructions=parser.get_format_instructions(),
        )
    )
    critique: OntologyUpdateCritique = parser.parse(response.content)

    if critique.ontology_update_success:
        state.clear_failure()
    else:
        state.set_failure(
            stage="The produced ontology did not pass the critique stage(conceptual issue).",
            reason=critique.ontology_update_critique_comment,
        )

    state.current_ontology.graph += state.ontology_addendum
    state.ontology_modified = True
    return state


def criticise_kg(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(KGUpdateCritique)

    prompt = """
        You are a helpful assistant that criticises the knowledge graph derived from the document with the help of a supporting ontology.
        You need to decide whether the knowledge graph derivation was faithful to the document.
        It is considered satisfactory if the knowledge graph captures all facts.

        Here is the supporting ontology:
        ```ttl
        {ontology}
        ```

        Here is the document from which the ontology was update was derived:
        {document}

        Here's the knowledge graph of facts derived from the document:
        ```ttl
        {knowledge_graph}
        ```

        {format_instructions}
    """

    prompt = PromptTemplate(
        template=prompt,
        input_variables=[
            "ontology",
            "document",
            "knowledge_graph",
            "format_instructions",
        ],
    )

    response = llm_tool.llm(
        prompt.format_prompt(
            ontology=state.current_ontology.graph.serialize(format="turtle"),
            document=state.input_text,
            knowledge_graph=state.current_graph.serialize(format="turtle"),
            format_instructions=parser.get_format_instructions(),
        )
    )
    critique: KGUpdateCritique = parser.parse(response.content)

    if critique.kg_update_success:
        state.clear_failure()
    else:
        state.set_failure(
            stage="The produced knowledge graph did not pass the critique stage(conceptual issue).",
            reason=critique.kg_update_critique_comment,
        )
    return state


def update_kg(state: AgentState) -> AgentState:
    """Update the knowledge graph with the new facts"""
    # Actual implementation to modify state
    # ...
    return state


def handle_visits(state: AgentState, node_name: str) -> tuple[AgentState, str]:
    """
    Handle visit counting for a node.

    Args:
        state: The current agent state
        node_name: The name of the node being visited

    Returns:
        tuple[AgentState, str]: Updated state and next node to execute
    """
    # Initialize visit count for this node if not exists
    if node_name not in state.node_visits:
        state.node_visits[node_name] = 0

    # Increment visit count
    state.node_visits[node_name] += 1
    logger.info(
        f"Visiting {node_name} (visit {state.node_visits[node_name]}/{state.max_visits})"
    )

    # Check if we've exceeded max visits
    if state.node_visits[node_name] > state.max_visits:
        logger.error(f"Maximum visits exceeded for {node_name}")
        state.set_failure(node_name, "Maximum visits exceeded")
        return state, END

    return state, node_name


def create_visit_route(success_node: str, current_node: str):
    """
    Create a route function with visit counting.

    Args:
        success_node: Node to go to on success
        current_node: Current node being visited

    Returns:
        A function that handles routing with visit counting
    """

    def route(state: AgentState) -> str:
        if state.status == Status.SUCCESS:
            state.clear_failure()  # Clear any previous failure state
            return success_node
        else:
            return handle_visits(state, current_node)[1]

    return route


def project_text_to_triples_route(state: AgentState) -> str:
    """Route function for text to triples node with visit counting."""
    return create_visit_route("Sublimate Ontology", "Text to Triples")(state)


def sublimate_ontology_route(state: AgentState) -> str:
    """Route function for sublimate ontology node with visit counting."""
    return create_visit_route("Criticise Ontology Update", "Sublimate Ontology")(state)


def criticise_ontology_update_route(state: AgentState) -> str:
    """Route function for criticise ontology update node with visit counting."""
    return create_visit_route("Criticise KG", "Criticise Ontology Update")(state)


def criticise_kg_route(state: AgentState) -> str:
    """Route function for criticise KG node with visit counting."""
    return create_visit_route("Update KG", "Criticise KG")(state)


# Define the workflow graph
def create_agent_graph():
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node("Select Ontology", select_ontology)
    workflow.add_node("Text to Triples", project_text_to_triples_with_ontology)
    workflow.add_node("Sublimate Ontology", sublimate_ontology)
    workflow.add_node("Criticise Ontology Update", criticise_ontology_update)
    workflow.add_node("Criticise KG", criticise_kg)
    workflow.add_node("Update KG", update_kg)

    # Standard edges
    workflow.add_edge(START, "Select Ontology")
    workflow.add_edge("Select Ontology", "Text to Triples")
    workflow.add_edge("Update KG", END)

    # Add conditional edges with visit counting
    workflow.add_conditional_edges(
        "Text to Triples",
        project_text_to_triples_route,
        {
            Status.SUCCESS: "Sublimate Ontology",
            Status.FAILED: "Text to Triples",
        },
    )

    workflow.add_conditional_edges(
        "Sublimate Ontology",
        sublimate_ontology_route,
        {
            Status.SUCCESS: "Criticise Ontology Update",
            Status.FAILED: "Text to Triples",
        },
    )

    workflow.add_conditional_edges(
        "Criticise Ontology Update",
        criticise_ontology_update_route,
        {
            Status.SUCCESS: "Criticise KG",
            Status.FAILED: "Text to Triples",
        },
    )

    workflow.add_conditional_edges(
        "Criticise KG",
        criticise_kg_route,
        {
            Status.SUCCESS: "Update KG",
            Status.FAILED: "Text to Triples",
        },
    )

    return workflow.compile()
