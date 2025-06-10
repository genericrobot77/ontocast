import logging

from ontocast.onto import (
    AgentState,
    Ontology,
    FailureStages,
    ONTOLOGY_VOID_ID,
)
from langchain.prompts import PromptTemplate
from ontocast.toolbox import ToolBox

from ontocast.prompt.render_ontology import (
    template_prompt,
    ontology_instruction_update,
    ontology_instruction_fresh,
    specific_ontology_instruction_fresh,
    specific_ontology_instruction_update,
    instructions,
    failure_instruction,
)

logger = logging.getLogger(__name__)


def render_onto_triples(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Starting ontology triples rendering process")
    llm_tool = tools.llm

    parser = llm_tool.get_parser(Ontology)

    logger.debug(f"Using domain: {state.current_domain}")

    if state.current_ontology.short_name == ONTOLOGY_VOID_ID:
        logger.debug("Creating fresh ontology")
        ontology_instruction = ontology_instruction_fresh
        specific_ontology_instruction = specific_ontology_instruction_fresh.format(
            current_domain=state.current_domain
        )
    else:
        ontology_iri = state.current_ontology.iri
        ontology_str = state.current_ontology.graph.serialize(format="turtle")
        ontology_desc = state.current_ontology.describe()
        ontology_instruction = ontology_instruction_update.format(
            ontology_iri=ontology_iri,
            ontology_desc=ontology_desc,
            ontology_str=ontology_str,
        )
        specific_ontology_instruction = specific_ontology_instruction_update.format(
            ontology_namespace=state.current_ontology.namespace
        )

    _instructions = instructions.format(
        specific_ontology_instruction=specific_ontology_instruction
    )

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

    if state.failure_reason is not None:
        _failure_instruction = failure_instruction.format(
            failure_stage=state.failure_stage,
            failure_reason=state.failure_reason,
        )
    else:
        _failure_instruction = ""

    try:
        response = llm_tool(
            prompt.format_prompt(
                text=state.current_chunk.text,
                instructions=_instructions,
                ontology_instruction=ontology_instruction,
                failure_instruction=_failure_instruction,
                format_instructions=parser.get_format_instructions(),
            )
        )

        proj_ontology = parser.parse(response.content)
        # check that the returned ontology name aligns with the candidate ontology name
        state.ontology_addendum = proj_ontology
        state.clear_failure()
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure(FailureStages.PARSE_TEXT_TO_ONTOLOGY_TRIPLES, str(e))
        return state
