import logging
from src.onto import AgentState, FailureStages, OntologyUpdateCritiqueReport
from src.onto import ONTOLOGY_VOID_IRI
from src.tools import ToolBox, LLMTool, OntologyManager
from src.prompts.criticise_ontology import prompt_fresh, prompt_update

from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)


def create_ontology_critic(tools: ToolBox):
    def _critique(state: AgentState) -> AgentState:
        logger.debug("Starting ontology critique process")
        llm_tool: LLMTool = tools.llm
        om_tool: OntologyManager = tools.ontology_manager
        parser = llm_tool.get_parser(OntologyUpdateCritiqueReport)

        if state.current_ontology.iri == ONTOLOGY_VOID_IRI:
            prompt = prompt_fresh
            ontology_original_str = ""
        else:
            ontology_original_str = f"""Here is the original ontology:\n```ttl\n{state.current_ontology.graph.serialize(format="turtle")}\n```"""
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
                ontology_update=state.ontology_addendum.graph.serialize(
                    format="turtle"
                ),
                document=state.input_text,
                format_instructions=parser.get_format_instructions(),
                ontology_original_str=ontology_original_str,
            )
        )
        critique: OntologyUpdateCritiqueReport = parser.parse(response.content)
        logger.debug(
            f"Parsed critique report - Success: {critique.ontology_update_success}, Score: {critique.ontology_update_score}"
        )

        if state.current_ontology.iri == ONTOLOGY_VOID_IRI:
            logger.debug("Adding new ontology to manager")
            om_tool.ontologies.append(state.ontology_addendum)
            state.current_ontology = state.ontology_addendum
        else:
            logger.debug(
                f"Updating existing ontology: {state.current_ontology.short_name}"
            )
            om_tool.update_ontology(
                state.current_ontology.short_name, state.ontology_addendum
            )

        if critique.ontology_update_success:
            logger.debug("Ontology critique successful, clearing failure state")
            state.clear_failure()
        else:
            logger.debug("Ontology critique failed, setting failure state")
            state.set_failure(
                stage=FailureStages.FAILED_AT_ONTOLOGY_CRITIQUE,
                reason=critique.ontology_update_critique_comment,
                success_score=critique.ontology_update_score,
            )

        return state

    return _critique
