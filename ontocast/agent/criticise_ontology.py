import logging

from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

from ontocast.onto import (
    ONTOLOGY_VOID_IRI,
    AgentState,
    FailureStages,
    OntologyUpdateCritiqueReport,
    Status,
)
from ontocast.prompt.criticise_ontology import prompt_fresh, prompt_update
from ontocast.tool import LLMTool, OntologyManager
from ontocast.toolbox import ToolBox

logger = logging.getLogger(__name__)


def criticise_ontology(state: AgentState, tools: ToolBox) -> AgentState:
    logger.info("Criticize ontology")
    llm_tool: LLMTool = tools.llm
    om_tool: OntologyManager = tools.ontology_manager
    parser = PydanticOutputParser(pydantic_object=OntologyUpdateCritiqueReport)

    if state.current_chunk is None:
        state.status = Status.FAILED
        return state

    if state.current_ontology.iri == ONTOLOGY_VOID_IRI:
        prompt = prompt_fresh
        ontology_original_str = ""
    else:
        ontology_original_str = (
            f"Here is the original ontology:"
            f"\n```ttl\n{state.current_ontology.graph.serialize(format='turtle')}\n```"
        )
        prompt = prompt_update

    prompt = PromptTemplate(
        template=prompt,
        input_variables=[
            "ontology_update",
            "document",
            "format_instructions",
            "ontology_original_str",
        ],
    )

    response = llm_tool(
        prompt.format_prompt(
            ontology_update=state.ontology_addendum.graph.serialize(format="turtle"),
            document=state.current_chunk.text,
            format_instructions=parser.get_format_instructions(),
            ontology_original_str=ontology_original_str,
        )
    )
    critique: OntologyUpdateCritiqueReport = parser.parse(response.content)
    logger.debug(
        f"Parsed critique report status: {critique.ontology_update_success}, "
        f"score: {critique.ontology_update_score}"
    )

    if state.current_ontology.iri == ONTOLOGY_VOID_IRI:
        logger.debug("Adding new ontology to manager")
        om_tool.ontologies.append(state.ontology_addendum)
        state.current_ontology = state.ontology_addendum
    else:
        logger.info(f"Updating existing ontology: {state.current_ontology.short_name}")
        om_tool.update_ontology(
            state.current_ontology.short_name, state.ontology_addendum.graph
        )

    if critique.ontology_update_success:
        logger.info("Ontology critique successful, clearing failure state")
        state.clear_failure()
    else:
        logger.info("Ontology critique failed, setting failure state")
        state.set_failure(
            stage=FailureStages.ONTOLOGY_CRITIQUE,
            reason=critique.ontology_update_critique_comment,
            success_score=critique.ontology_update_score,
        )

    return state
