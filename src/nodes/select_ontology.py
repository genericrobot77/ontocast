from src.onto import AgentState, OntologySelectorReport
from langchain.prompts import PromptTemplate


def create_ontology_selector(tools):
    def _selector(state: AgentState) -> AgentState:
        llm_tool = tools["llm"]
        parser = llm_tool.get_parser(OntologySelectorReport)

        ontologies_desc = "\n\n".join([o.describe() for o in state.ontologies])
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

        if selector.short_name in state.ontology_names:
            state.current_ontology_name = selector.short_name
        return state

    return _selector
