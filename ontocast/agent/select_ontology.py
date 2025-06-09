import logging
from ontocast.onto import AgentState, OntologySelectorReport
from langchain.prompts import PromptTemplate
from ontocast.tool import OntologyManager
from ontocast.toolbox import ToolBox
from ontocast.prompt.select_ontology import template_prompt
from ontocast.onto import FailureStages

logger = logging.getLogger(__name__)


def select_ontology(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that selects the most appropriate ontology for the input text."""
    logger.debug("Starting ontology selection process")
    llm_tool = tools.llm
    om_tool: OntologyManager = tools.ontology_manager

    parser = llm_tool.get_parser(OntologySelectorReport)

    ontologies_desc = "\n\n".join([o.describe() for o in om_tool.ontologies])
    logger.debug(f"Retrieved descriptions for {len(om_tool.ontologies)} ontologies")

    if state.current_chunk is None:
        if state.chunks:
            state.current_chunk = state.chunks.pop(0)
        else:
            state.set_failure(
                FailureStages.NO_CHUNKS_TO_PROCESS, "No chunks to process"
            )
    excerpt = state.current_chunk.text[:1000] + "..."

    prompt = PromptTemplate(
        template=template_prompt,
        input_variables=["excerpt", "ontologies_desc", "format_instructions"],
    )

    response = llm_tool(
        prompt.format_prompt(
            excerpt=excerpt,
            ontologies_desc=ontologies_desc,
            format_instructions=parser.get_format_instructions(),
        )
    )
    selector = parser.parse(response.content)
    logger.debug(f"Parsed selector report - Selected ontology: {selector.short_name}")

    state.current_ontology = om_tool.get_ontology(selector.short_name)
    logger.debug(f"Set current ontology to: {selector.short_name}")
    return state
