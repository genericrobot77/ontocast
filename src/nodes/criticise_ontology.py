from src.onto import AgentState, FailureStages, OntologyUpdateCritiqueReport
from src.onto import ToolType
from src.tools import OntologyManager, LLMTool


from langchain.prompts import PromptTemplate


def create_ontology_critic(tools):
    def _critique(state: AgentState) -> AgentState:
        llm_tool: LLMTool = tools[ToolType.LLM]
        om_tool: OntologyManager = tools[ToolType.ONTOLOGY_MANAGER]
        parser = llm_tool.get_parser(OntologyUpdateCritiqueReport)

        if state.current_ontology is None:
            prompt = """        
    You are a helpful assistant that criticises a newly proposed ontology.
    You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
    The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
    If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
    As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.

    Here is the document from which the ontology was update was derived:
    {document}

    Here is the proposed ontology:
    ```ttl
    {ontology_update}
    ```

    {format_instructions}
    """

        else:
            prompt = f"""

    You are a helpful assistant that criticises an ontology update.
    You need to decide whether the updated ontology is sufficiently complete and comprehensive, also providing a score between 0 and 100.
    The ontology is considered complete and comprehensive if it captures the most important abstract classes and properties that are present explicitly or implicitly in the document.
    If is not not complete and comprehensive, provide a very concrete itemized explanation of why can be improved.
    As we are working on an ontology, ONLY abstract classes and properties are considered, concrete entities are not important.


    Here is the original ontology:
    ```ttl
    {state.current_ontology.graph.serialize(format="turtle")}
    ```

    Here is the document from which the ontology was update was derived:
    {{document}}

    Here is the ontology update:
    ```ttl
    {{ontology_update}}
    ```

    {{format_instructions}}
    """

        prompt = PromptTemplate(
            template=prompt,
            input_variables=[
                "ontology_update",
                "document",
                "format_instructions",
            ],
        )

        response = llm_tool.llm(
            prompt.format_prompt(
                ontology_update=state.ontology_addendum.graph.serialize(
                    format="turtle"
                ),
                document=state.input_text,
                format_instructions=parser.get_format_instructions(),
            )
        )
        critique: OntologyUpdateCritiqueReport = parser.parse(response.content)

        if state.current_ontology is None:
            om_tool.ontologies.append(state.ontology_addendum)
            state.current_ontology = state.ontology_addendum
        else:
            om_tool.update_ontology(
                state.current_ontology.short_name, state.ontology_addendum
            )

        if critique.ontology_update_success:
            state.clear_failure()
        else:
            state.set_failure(
                stage=FailureStages.FAILED_AT_ONTOLOGY_CRITIQUE,
                reason=critique.ontology_update_critique_comment,
                success_score=critique.ontology_update_score,
            )

        return state

    return _critique
