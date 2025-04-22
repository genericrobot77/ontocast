from src.onto import AgentState, OntologySelectorReport
from langchain.prompts import PromptTemplate
from src.onto import ToolType
from src.tools import OntologyManager


def create_ontology_selector(tools):
    def _selector(state: AgentState) -> AgentState:
        llm_tool = tools[ToolType.LLM]
        om_tool: OntologyManager = tools[ToolType.ONTOLOGY_MANAGER]

        parser = llm_tool.get_parser(OntologySelectorReport)

        ontologies_desc = "\n\n".join([o.describe() for o in om_tool.ontologies])
        excerpt = state.input_text[:1000] + "..."

        prompt = """
            You are a helpful assistant that decides which ontology to use for a given document.
            You are given a list of ontologies and a document.
            You need to decide which ontology can be used for the document to create a semantic graph.
            Here is the list of ontologies:
            {ontologies_desc}
            
            Here is an excerpt from the document:
            {excerpt}

            {format_instructions}
        """

        prompt = PromptTemplate(
            template=prompt,
            input_variables=["excerpt", "ontologies_desc", "format_instructions"],
        )

        response = llm_tool.llm(
            prompt.format_prompt(
                excerpt=excerpt,
                ontologies_desc=ontologies_desc,
                format_instructions=parser.get_format_instructions(),
            )
        )
        selector = parser.parse(response.content)

        state.current_ontology = om_tool.get_ontology(selector.short_name)
        return state

    return _selector
