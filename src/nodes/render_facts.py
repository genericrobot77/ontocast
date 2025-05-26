import logging
import os

from src.onto import AgentState, FailureStages, SemanticTriplesFactsReport
from langchain.prompts import PromptTemplate
from src.util import get_document_hash
from src.onto import DEFAULT_DOMAIN
from src.prompts.render_facts import ontology_instruction, template_prompt
from src.tools import ToolBox

logger = logging.getLogger(__name__)


def create_facts_renderer(state: AgentState, tools: ToolBox):
    logger.debug("Starting facts rendering process")
    llm_tool = tools.llm

    parser = llm_tool.get_parser(SemanticTriplesFactsReport)

    ontology_iri = state.current_ontology.iri
    ontology_str = state.current_ontology.graph.serialize(format="turtle")

    # Extract ontology extension from IRI
    ontology_ext = ontology_iri.split("/")[-1].split("#")[0]
    if not ontology_ext:
        ontology_ext = "default"
    logger.debug(f"Extracted ontology extension: {ontology_ext}")

    # Generate document hash
    doc_hash = get_document_hash(state.input_text)
    logger.debug(f"Generated document hash: {doc_hash}")

    current_domain = os.getenv("CURRENT_DOMAIN", DEFAULT_DOMAIN)
    logger.debug(f"Using domain: {current_domain}")

    # Construct namespace with domain, ontology extension and hash
    state.current_namespace = f"{current_domain}/{ontology_ext}/{doc_hash}/"
    logger.debug(f"Set current namespace to: {state.current_namespace}")

    ontology_instruction_str = ontology_instruction.format(
        ontology_iri=ontology_iri, ontology_str=ontology_str
    )
    template_prompt_str = template_prompt

    prompt = PromptTemplate(
        template=template_prompt_str,
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

        response = llm_tool(
            prompt.format_prompt(
                ontology_iri=ontology_iri,
                current_namespace=state.current_namespace,
                text=state.input_text,
                ontology_instruction=ontology_instruction_str,
                failure_instruction=failure_instruction,
                format_instructions=parser.get_format_instructions(),
            )
        )

        proj = parser.parse(response.content)
        state.graph_facts += proj.semantic_graph
        state.clear_failure()
        return state

    except Exception as e:
        logger.error(f"Failed to generate triples: {str(e)}")
        state.set_failure(FailureStages.FAILED_AT_PARSE_TEXT_TO_FACTS_TRIPLES, str(e))
        return state
