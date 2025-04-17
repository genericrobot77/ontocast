import logging


from src.onto import (
    AgentState,
    Ontology,
    FailureStages,
)
from langchain.prompts import PromptTemplate

from src.config import CURRENT_DOMAIN

logger = logging.getLogger(__name__)


def create_onto_triples_renderer(tools):
    def _renderer(state: AgentState) -> AgentState:
        llm_tool = tools["llm"]

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
        - assign where possible correct units to numeric literals.
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

    return _renderer
