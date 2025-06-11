import logging

from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate

from ontocast.onto import AgentState, FailureStages, KGCritiqueReport
from ontocast.prompt.criticise_facts import prompt as criticise_facts_prompt
from ontocast.toolbox import ToolBox

logger = logging.getLogger(__name__)


def criticise_facts(state: AgentState, tools: ToolBox) -> AgentState:
    logger.info("Criticize facts")

    llm_tool = tools.llm
    parser = PydanticOutputParser(pydantic_object=KGCritiqueReport)

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
            document=state.current_chunk.text,
            knowledge_graph=state.current_chunk.graph.serialize(format="turtle"),
            format_instructions=parser.get_format_instructions(),
        )
    )
    critique: KGCritiqueReport = parser.parse(response.content)
    logger.debug(
        f"Parsed critique report - success: {critique.facts_graph_derivation_success}, "
        f"score: {critique.facts_graph_derivation_score}"
    )

    if critique.facts_graph_derivation_success:
        logger.debug("Facts critique successful, clearing failure state")
        state.chunks_processed.append(state.current_chunk)
        state.clear_failure()
    else:
        logger.debug("Facts critique failed, setting failure state")
        state.set_failure(
            stage=FailureStages.FACTS_CRITIQUE,
            reason=critique.facts_graph_derivation_critique_comment,
            success_score=critique.facts_graph_derivation_score,
        )
    return state
