import logging
from functools import partial

from aot_cast.agent.criticise_facts import criticise_facts
from aot_cast.agent.criticise_ontology import criticise_ontology
from aot_cast.agent.render_facts import render_facts
from aot_cast.agent.render_ontology_triples import render_onto_triples
from aot_cast.agent.save_kg import save_kg
from aot_cast.agent.select_ontology import select_ontology
from aot_cast.agent.sublimate_ontology import sublimate_ontology
from aot_cast.agent.convert_document import convert_document
from aot_cast.agent.chunk_text import chunk_text
from aot_cast.agent.check_chunks import check_chunks_empty
from aot_cast.onto import AgentState, Status, WorkflowNode
from aot_cast.tool import ToolBox
from aot_cast.util import wrap_with, count_visits


from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


logger = logging.getLogger(__name__)


def add_conditional_with_visit_counter_logic(
    workflow: StateGraph,
    current_node: WorkflowNode,
    mapping: dict[Status, WorkflowNode],
):
    def route(state: AgentState) -> Status:
        # Initialize visit count if not exists

        logger.info(
            f"Making decision after {current_node} visit: visit {state.node_visits[current_node]}/{state.max_visits}, "
            f"onto: {len(state.current_ontology.graph)}, facts: {len(state.graph_facts)}"
        )
        logger.info(f"Current node_visits state: {state.node_visits}")

        if state.status == Status.SUCCESS:
            state.clear_failure()
            return state.status

        if state.node_visits[current_node] >= state.max_visits:
            logger.error(f"Maximum visits exceeded for {current_node}")
            state.set_failure(current_node, "Maximum visits exceeded")
            return Status.SUCCESS
        else:
            return Status.FAILED

    workflow.add_conditional_edges(current_node, route, mapping)


def create_agent_graph(tools: ToolBox) -> CompiledStateGraph:
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)

    # Create nodes with partial application of tools

    select_ontology_ = partial(select_ontology, tools=tools)
    convert_document_ = partial(convert_document, tools=tools)
    chunk_text_ = partial(chunk_text, tools=tools)
    check_chunks_empty_ = partial(check_chunks_empty)

    render_ontology_tuple = wrap_with(
        partial(render_onto_triples, tools=tools),
        WorkflowNode.TEXT_TO_ONTOLOGY,
        count_visits,
    )
    render_facts_tuple = wrap_with(
        partial(render_facts, tools=tools), WorkflowNode.TEXT_TO_FACTS, count_visits
    )
    criticise_ontology_tuple = wrap_with(
        partial(criticise_ontology, tools=tools),
        WorkflowNode.CRITICISE_ONTOLOGY,
        count_visits,
    )
    criticise_facts_tuple = wrap_with(
        partial(criticise_facts, tools=tools),
        WorkflowNode.CRITICISE_FACTS,
        count_visits,
    )
    sublimate_ontology_tuple = partial(sublimate_ontology, tools=tools)
    save_kg_tuple = partial(save_kg, tools=tools)

    # Add nodes using string values
    workflow.add_node(WorkflowNode.CONVERT_TO_MD, convert_document_)
    workflow.add_node(WorkflowNode.CHUNK, chunk_text_)

    workflow.add_node(WorkflowNode.SELECT_ONTOLOGY, select_ontology_)
    workflow.add_node(*render_ontology_tuple)
    workflow.add_node(*render_facts_tuple)
    workflow.add_node(WorkflowNode.SUBLIMATE_ONTOLOGY, sublimate_ontology_tuple)
    workflow.add_node(*criticise_ontology_tuple)
    workflow.add_node(*criticise_facts_tuple)
    workflow.add_node(WorkflowNode.CHUNKS_EMPTY, check_chunks_empty_)
    workflow.add_node(WorkflowNode.SAVE_KG, save_kg_tuple)

    # Standard edges using string values
    workflow.add_edge(START, WorkflowNode.CONVERT_TO_MD)
    workflow.add_edge(WorkflowNode.CONVERT_TO_MD, WorkflowNode.CHUNK)
    workflow.add_edge(WorkflowNode.CHUNK, WorkflowNode.SELECT_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SELECT_ONTOLOGY, WorkflowNode.TEXT_TO_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SUBLIMATE_ONTOLOGY, WorkflowNode.CRITICISE_FACTS)
    workflow.add_edge(WorkflowNode.SAVE_KG, END)

    workflow.add_conditional_edges(
        WorkflowNode.CHUNKS_EMPTY,
        lambda state: Status.SUCCESS if state.succes else Status.FAILED,
        {
            Status.SUCCESS: WorkflowNode.SAVE_KG,
            Status.FAILED: WorkflowNode.SELECT_ONTOLOGY,
        },
    )

    add_conditional_with_visit_counter_logic(
        workflow=workflow,
        current_node=WorkflowNode.TEXT_TO_ONTOLOGY,
        mapping={
            Status.SUCCESS: WorkflowNode.CRITICISE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    add_conditional_with_visit_counter_logic(
        workflow=workflow,
        current_node=WorkflowNode.CRITICISE_ONTOLOGY,
        mapping={
            Status.SUCCESS: WorkflowNode.TEXT_TO_FACTS,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    add_conditional_with_visit_counter_logic(
        workflow=workflow,
        current_node=WorkflowNode.TEXT_TO_FACTS,
        mapping={
            Status.SUCCESS: WorkflowNode.SUBLIMATE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    add_conditional_with_visit_counter_logic(
        workflow=workflow,
        current_node=WorkflowNode.CRITICISE_FACTS,
        mapping={
            Status.SUCCESS: WorkflowNode.CHUNKS_EMPTY,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    return workflow.compile()
