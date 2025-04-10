from rdflib import Namespace
import logging

from langgraph.graph import END, StateGraph, START
from enum import StrEnum

import re

from src.onto import (
    AgentState,
    OntologySelectorReport,
    Ontology,
    RDFGraph,
    Status,
    OntologyUpdateCritiqueReport,
    KGCritiqueReport,
    SemanticTriplesFactsReport,
    FailureStages,
)
from langchain.prompts import PromptTemplate

from src.tools import LLMTool
from src.config import CURRENT_NS_IRI, CURRENT_DOMAIN

logger = logging.getLogger(__name__)

# Create a global instance of the LLM tool
llm_tool = LLMTool()


def extract_struct(text, key):
    # Pattern to match text between ```key and ```
    pattern = rf"```{key}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def select_ontology(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(OntologySelectorReport)

    ontologies_desc = "\n\n".join([o.describe() for o in state.ontologies])
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


def render_ontology_triples(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(Ontology)

    if state.current_ontology_name is None:
        ontology_instruction = """
Develop a new domain ontology based on the document.
        
        """
        specific_ontology_instruction = f"""
    - all new abstract entities/classes/types or properties added to the new ontology must be linked to entities from basic ontologies (RDFS, OWL, schema etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
    - propose a succint IRI for the domain ontology, linked to the domain {CURRENT_DOMAIN}.
    - explicitly use prefix `co:` for entities/properties placed in the proposed ontology."""
    else:
        ontology_iri = state.current_ontology.iri
        ontology_str = state.current_ontology.graph.serialize(format="turtle")

        ontology_instruction = f"""
Update/complement the domain ontology <{ontology_iri}> provided below with abstract entities and relations that can be inferred from the document.

{state.current_ontology.describe()}
Feel free to modify the description of the ontology to make it more accurate and complete, but to change neither the ontology IRI nor name.

```ttl
{ontology_str}
```
"""

        specific_ontology_instruction = f"""
    - all new abstract entities/classes/types or properties added to <{ontology_iri}> ontology must be linked to entities from either domain ontology <{ontology_iri}> or basic ontologies (RDFS, OWL, schema etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc
    - add new constraints and axioms if needed."""

    instructions = f"""
Follow the instructions:

{specific_ontology_instruction}
    - ontology must be provided in turtle (ttl) format as a single string.
    - (IMPORTANT) define all prefixes for all namespaces used in the ontology, etc rdf, rdfs, owl, schema, etc.
    - do not add facts, or concrete entities from the document.
    - make sure newly introduced entites are well linked / described by their properties.
    - make sure that the semantic representation is faithful to the document, feel to use your knowledge and commone sense to make the ontology more complete and accurate.
    - feel free to update/assign the version of the ontology using semantic versioning convention.

    """

    template_prompt = """
{ontology_instruction}

{instructions}

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
            "text",
            "instructions",
            "ontology_instruction",
            "failure_instruction",
            "format_instructions",
        ],
    )

    try:
        if state.failure_reason is not None:
            failure_instruction = "IMPORTANT: The previous attempt to generate ontology triples failed/was unsatisfactory."
            if state.failure_stage is not None:
                failure_instruction += (
                    f"\n\nIt failed at the stage: {state.failure_stage}"
                )
            failure_instruction += f"\n\n{state.failure_reason}"
            failure_instruction += "\n\nPlease address ALL the issues outlined in the critique. We will be penalized :( for each unaddressed issue."
        else:
            failure_instruction = ""

        response = llm_tool.llm(
            prompt.format_prompt(
                text=state.input_text,
                instructions=instructions,
                ontology_instruction=ontology_instruction,
                failure_instruction=failure_instruction,
                format_instructions=parser.get_format_instructions(),
            )
        )

        proj_ontology = parser.parse(response.content)
        state.ontology_addendum = proj_ontology
        state.clear_failure()
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure(
            FailureStages.FAILED_AT_PARSE_TEXT_TO_ONTOLOGY_TRIPLES, str(e)
        )
        return state


def render_facts_triples(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(SemanticTriplesFactsReport)

    ontology_iri = state.current_ontology.iri
    ontology_str = state.current_ontology.graph.serialize(format="turtle")

    ontology_instruction = f"""
Use the following ontology <{state.current_ontology.iri}>:
    
```ttl
{ontology_str}
```
"""

    template_prompt = """
Generate semantic triples representing facts (not abstract entities) in turtle (ttl) format from the text below.

{ontology_instruction}
        
Follow the instructions:

    - use commonly known ontologies (RDFS, OWL, schema etc) and the provided ontology <{ontology_iri}> to place (define) entities/classes/types and relationships between them that can be inferred from the document.
    - for facts from the document, use <{current_namespace}> namespace with prefix `cd:` as `@prefix cd: {current_namespace} .`
    - all entities identified by <{current_namespace}> namespace (facts, less abstract entities) must be linked to entities from either domain ontology <{ontology_iri}> or basic ontologies (RDFS, OWL etc), e.g. rdfs:Class, rdfs:subClassOf, rdf:Property, rdfs:domain, owl:Restriction, schema:Person, schema:Organization, etc 
    - all facts should form a connect graph with respect to <{current_namespace}> namespace.
    - (IMPORTANT) define all prefixes for all namespaces used in the ontology, etc rdf, rdfs, owl, schema, etc.
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
            "ontology_iri",
            "current_namespace",
            "text",
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
                ontology_iri=ontology_iri,
                current_namespace=CURRENT_NS_IRI,
                text=state.input_text,
                ontology_instruction=ontology_instruction,
                failure_instruction=failure_instruction,
                format_instructions=parser.get_format_instructions(),
            )
        )

        proj = parser.parse(response.content)
        state.current_graph = proj.semantic_graph
        state.clear_failure()
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure(FailureStages.FAILED_AT_PARSE_TEXT_TO_FACTS_TRIPLES, str(e))
        return state


def _sublimate_ontology(state: AgentState):
    query_ontology = f"""
    PREFIX cd: <{CURRENT_NS_IRI}>
    
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
        PREFIX cd: <{CURRENT_NS_IRI}>

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
            if str(ns) == state.current_ontology.iri
        ]

        graph_onto_addendum.bind(
            ns_prefix_current_ontology[0], Namespace(state.current_ontology.iri)
        )
        graph_facts.bind(
            ns_prefix_current_ontology[0], Namespace(state.current_ontology.iri)
        )

        current_idx = next(
            i
            for i, o in enumerate(state.ontologies)
            if o.short_name == state.current_ontology_name
        )
        state.ontologies[current_idx] += graph_onto_addendum
        state.graph_facts = graph_facts
        state.clear_failure()
    except Exception as e:
        state.set_failure(
            FailureStages.FAILED_AT_SUBLIMATE_ONTOLOGY,
            str(e),
        )

    return state


def criticise_ontology_update(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(OntologyUpdateCritiqueReport)

    if state.current_ontology_name is None:
        prompt = """        
You are a helpful assistant that criticises a newly proposed ontology.
You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.

Here is the document from which the ontology was update was derived:
{document}

Here is the proposed ontology:
```ttl
{ontology_update}
```

{format_instructions}
"""

    else:
        prompt = f"""

You are a helpful assistant that criticises an ontology update.
You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.


Here is the original ontology:
```ttl
{state.current_ontology.graph.serialize(format="turtle")}
```

Here is the document from which the ontology was update was derived:
{{document}}

Here is the ontology update:
```ttl
{{ontology_update}}
```

{{format_instructions}}
"""

    prompt = PromptTemplate(
        template=prompt,
        input_variables=[
            "ontology_update",
            "document",
            "format_instructions",
        ],
    )

    response = llm_tool.llm(
        prompt.format_prompt(
            ontology_update=state.ontology_addendum.graph.serialize(format="turtle"),
            document=state.input_text,
            format_instructions=parser.get_format_instructions(),
        )
    )
    critique: OntologyUpdateCritiqueReport = parser.parse(response.content)

    if state.current_ontology_name is None:
        state.ontologies.append(state.ontology_addendum)
        state.current_ontology_name = state.ontology_addendum.short_name
    else:
        current_idx = next(
            i
            for i, o in enumerate(state.ontologies)
            if o.short_name == state.current_ontology_name
        )
        state.ontologies[current_idx] += state.ontology_addendum

    if critique.ontology_update_success:
        state.clear_failure()
    else:
        state.set_failure(
            stage=FailureStages.FAILED_AT_ONTOLOGY_CRITIQUE,
            reason=critique.ontology_update_critique_comment,
            success_score=critique.ontology_update_score,
        )

    return state


def criticise_facts(state: AgentState) -> AgentState:
    parser = llm_tool.get_parser(KGCritiqueReport)

    prompt = """
        You are a helpful assistant that criticises the knowledge graph derived from the document with the help of a supporting ontology.
        You need to decide whether the knowledge graph of facts was derived faithfully from the document.
        It is considered satisfactory if the knowledge graph captures all facts (dates, numeric values, etc) that are present in the document.
        Another criterion is that the knowledge graph is connected.

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
    critique: KGCritiqueReport = parser.parse(response.content)

    if critique.facts_graph_derivation_success:
        state.current_graph = critique.kg_update_graph
        state.clear_failure()
    else:
        state.set_failure(
            stage=FailureStages.FAILED_AT_FACTS_CRITIQUE,
            reason=critique.kg_update_critique_comment,
        )
    return state


def load_kg(state: AgentState) -> AgentState:
    """Update the knowledge graph with the new facts"""
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


class WorkflowNode(StrEnum):
    SELECT_ONTOLOGY = "Select Ontology"
    TEXT_TO_ONTOLOGY = "Text to Ontology"
    TEXT_TO_FACTS = "Text to Facts"
    SUBLIMATE_ONTOLOGY = "Sublimate Ontology"
    CRITICISE_ONTOLOGY = "Criticise Ontology"
    CRITICISE_FACTS = "Criticise Facts"
    LOAD_KG = "Load KG"


# Define the workflow graph
def create_agent_graph():
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node(WorkflowNode.SELECT_ONTOLOGY, select_ontology)
    workflow.add_node(WorkflowNode.TEXT_TO_ONTOLOGY, render_ontology_triples)
    workflow.add_node(WorkflowNode.TEXT_TO_FACTS, render_facts_triples)
    workflow.add_node(WorkflowNode.SUBLIMATE_ONTOLOGY, sublimate_ontology)
    workflow.add_node(WorkflowNode.CRITICISE_ONTOLOGY, criticise_ontology_update)
    workflow.add_node(WorkflowNode.CRITICISE_FACTS, criticise_facts)
    workflow.add_node(WorkflowNode.LOAD_KG, load_kg)

    # Standard edges
    workflow.add_edge(START, WorkflowNode.SELECT_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SELECT_ONTOLOGY, WorkflowNode.TEXT_TO_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SUBLIMATE_ONTOLOGY, WorkflowNode.CRITICISE_FACTS)

    workflow.add_edge(WorkflowNode.LOAD_KG, END)

    # Add conditional edges with visit counting
    workflow.add_conditional_edges(
        WorkflowNode.TEXT_TO_ONTOLOGY,
        project_text_to_triples_route,
        {
            Status.SUCCESS: WorkflowNode.CRITICISE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.CRITICISE_ONTOLOGY,
        sublimate_ontology_route,
        {
            Status.SUCCESS: WorkflowNode.TEXT_TO_FACTS,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.TEXT_TO_FACTS,
        criticise_ontology_update_route,
        {
            Status.SUCCESS: WorkflowNode.SUBLIMATE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.CRITICISE_FACTS,
        criticise_kg_route,
        {
            Status.SUCCESS: WorkflowNode.LOAD_KG,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    return workflow.compile()
