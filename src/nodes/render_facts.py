import logging


from src.onto import AgentState, FailureStages, SemanticTriplesFactsReport
from langchain.prompts import PromptTemplate
from src.util import get_document_hash
from src.config import CURRENT_DOMAIN

logger = logging.getLogger(__name__)


def create_facts_renderer(tools):
    def _renderer(state: AgentState) -> AgentState:
        llm_tool = tools["llm"]

        parser = llm_tool.get_parser(SemanticTriplesFactsReport)

        ontology_iri = state.current_ontology.iri
        ontology_str = state.current_ontology.graph.serialize(format="turtle")

        # Extract ontology extension from IRI
        ontology_ext = ontology_iri.split("/")[-1].split("#")[0]
        if not ontology_ext:
            ontology_ext = "default"

        # Generate document hash
        doc_hash = get_document_hash(state.input_text)

        # Construct namespace with domain, ontology extension and hash
        current_namespace = f"{CURRENT_DOMAIN}/{ontology_ext}/{doc_hash}/"

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
        - pay attention to correct formatting of literals, e.g. dates, currencies. Numeric literals should be formatted using double quotes, when they are typed with `^^`, for example `fsec:hasRevenue "13"^^xsd:decimal ;`
        - make semantic representation of facts as atomic (!!!) as possible.
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
                failure_instruction += "\n\nPlease fix the errors and do your best to generate triples again."
            else:
                failure_instruction = ""

            response = llm_tool.llm(
                prompt.format_prompt(
                    ontology_iri=ontology_iri,
                    current_namespace=current_namespace,
                    text=state.input_text,
                    ontology_instruction=ontology_instruction,
                    failure_instruction=failure_instruction,
                    format_instructions=parser.get_format_instructions(),
                )
            )

            proj = parser.parse(response.content)
            if state.graph_facts is None:
                state.graph_facts = proj.semantic_graph
            else:
                state.graph_facts += proj.semantic_graph
            state.clear_failure()
            return state

        except Exception as e:
            logger.error(f"Failed to generate triples: {str(e)}")
            state.set_failure(
                FailureStages.FAILED_AT_PARSE_TEXT_TO_FACTS_TRIPLES, str(e)
            )
            return state

    return _renderer
