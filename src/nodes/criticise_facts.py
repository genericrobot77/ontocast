from src.onto import AgentState, FailureStages, KGCritiqueReport


from langchain.prompts import PromptTemplate


def create_facts_critic(tools) -> AgentState:
    def _renderer(state: AgentState) -> AgentState:
        llm_tool = tools["llm"]
        parser = llm_tool.get_parser(KGCritiqueReport)

        prompt = """
    You are a helpful assistant that criticises the knowledge graph of facts derived from a document using a supporting ontology.
    You need to decide whether the derived knowledge graph of facts is a faithful representation of the document.
    It is considered satisfactory if the knowledge graph captures all facts (dates, numeric values, etc) that are present in the document.
    Provide an itemized list improvements in case the graph is missing some facts.

    Here is the supporting ontology:
    ```ttl
    {ontology}
    ```

    Here is the document from which the ontology was update was derived:
    {document}

    Here's the knowledge graph of facts derived from the document:
    ```ttl
    {knowledge_graph}
    ```

    {format_instructions}"""

        prompt = PromptTemplate(
            template=prompt,
            input_variables=[
                "ontology",
                "document",
                "knowledge_graph",
                "format_instructions",
            ],
        )

        response = llm_tool.llm(
            prompt.format_prompt(
                ontology=state.current_ontology.graph.serialize(format="turtle"),
                document=state.input_text,
                knowledge_graph=state.graph_facts.serialize(format="turtle"),
                format_instructions=parser.get_format_instructions(),
            )
        )
        critique: KGCritiqueReport = parser.parse(response.content)

        if critique.facts_graph_derivation_success:
            state.clear_failure()
        else:
            state.set_failure(
                stage=FailureStages.FAILED_AT_FACTS_CRITIQUE,
                reason=critique.facts_graph_derivation_critique_comment,
                success_score=critique.facts_graph_derivation_score,
            )
        return state

    return _renderer
