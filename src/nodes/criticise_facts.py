from src.onto import AgentState, FailureStages, KGCritiqueReport

from src.onto import ToolType
from langchain.prompts import PromptTemplate
from src.prompts.criticise_facts import prompt as criticise_facts_prompt


def create_facts_critic(tools):
    def _renderer(state: AgentState) -> AgentState:
        llm_tool = tools[ToolType.LLM]
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
