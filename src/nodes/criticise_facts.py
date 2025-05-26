import logging
from src.onto import AgentState, FailureStages, KGCritiqueReport
from langchain.prompts import PromptTemplate
from src.prompts.criticise_facts import prompt as criticise_facts_prompt
from src.tools import ToolBox

logger = logging.getLogger(__name__)


def create_facts_critic(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Starting facts critique process")
    llm_tool = tools.llm
    parser = llm_tool.get_parser(KGCritiqueReport)

    prompt = PromptTemplate(
        template=criticise_facts_prompt,
        input_variables=[
            "ontology",
            "document",
            "knowledge_graph",
            "format_instructions",
        ],
    )

    response = llm_tool(
        prompt.format_prompt(
            ontology=state.current_ontology.graph.serialize(format="turtle"),
            document=state.input_text,
            knowledge_graph=state.graph_facts.serialize(format="turtle"),
            format_instructions=parser.get_format_instructions(),
        )
    )
    critique: KGCritiqueReport = parser.parse(response.content)
    logger.debug(
        f"Parsed critique report - Success: {critique.facts_graph_derivation_success}, Score: {critique.facts_graph_derivation_score}"
    )

    if critique.facts_graph_derivation_success:
        logger.debug("Facts critique successful, clearing failure state")
        state.clear_failure()
    else:
        logger.debug("Facts critique failed, setting failure state")
        state.set_failure(
            stage=FailureStages.FAILED_AT_FACTS_CRITIQUE,
            reason=critique.facts_graph_derivation_critique_comment,
            success_score=critique.facts_graph_derivation_score,
        )
    return state
