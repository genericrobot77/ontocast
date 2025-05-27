import logging
from aot_cast.onto import AgentState, OntologySelectorReport
from langchain.prompts import PromptTemplate
from aot_cast.tools import OntologyManager, ToolBox
from aot_cast.prompts.select_ontology import template_prompt

logger = logging.getLogger(__name__)


def select_ontology(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that selects the most appropriate ontology for the input text."""
    logger.debug("Starting ontology selection process")
    llm_tool = tools.llm
    om_tool: OntologyManager = tools.ontology_manager

    parser = llm_tool.get_parser(OntologySelectorReport)

    ontologies_desc = "\n\n".join([o.describe() for o in om_tool.ontologies])
    logger.debug(f"Retrieved descriptions for {len(om_tool.ontologies)} ontologies")

    excerpt = state.input_text[:1000] + "..."

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
