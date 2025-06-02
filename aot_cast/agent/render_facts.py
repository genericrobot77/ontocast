import logging

from aot_cast.onto import AgentState, FailureStages, SemanticTriplesFactsReport
from langchain.prompts import PromptTemplate
from aot_cast.prompt.render_facts import (
    ontology_instruction,
    template_prompt as template_prompt_str,
)
from aot_cast.tool import ToolBox

logger = logging.getLogger(__name__)


def render_facts(state: AgentState, tools: ToolBox):
    logger.debug("Starting facts rendering process")
    llm_tool = tools.llm

    parser = llm_tool.get_parser(SemanticTriplesFactsReport)

    ontology_str = state.current_ontology.graph.serialize(format="turtle")

    ontology_instruction_str = ontology_instruction.format(
        ontology_iri=state.current_ontology.iri, ontology_str=ontology_str
    )

    prompt = PromptTemplate(
        template=template_prompt_str,
        input_variables=[
            "ontology_namespace",
            "current_doc_namespace",
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

        response = llm_tool(
            prompt.format_prompt(
                ontology_namespace=state.current_ontology.namespace,
                current_doc_namespace=state.current_chunk.namespace,
                text=state.current_chunk.text,
                ontology_instruction=ontology_instruction_str,
                failure_instruction=failure_instruction,
                format_instructions=parser.get_format_instructions(),
            )
        )

        proj = parser.parse(response.content)
        state.current_chunk.graph += proj.semantic_graph

        state.clear_failure()
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure(FailureStages.FAILED_AT_PARSE_TEXT_TO_FACTS_TRIPLES, str(e))
        return state
