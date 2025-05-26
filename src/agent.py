import logging

from langgraph.graph import END, StateGraph, START
from langgraph.graph.state import CompiledStateGraph
from functools import partial
from src.util import add_counter

from src.onto import (
    AgentState,
    Status,
    WorkflowNode,
)
from src.tools import ToolBox

from .nodes import (
    create_ontology_selector,
    create_onto_triples_renderer,
    create_facts_renderer,
    create_facts_critic,
    create_ontology_critic,
    create_kg_saver,
    create_ontology_sublimator,
)
from src.nodes.update_ontology_properties import update_ontology_manager

logger = logging.getLogger(__name__)


def init_toolbox(toolbox: ToolBox):
    toolbox.ontology_manager.ontologies = (
        toolbox.triple_store_manager.fetch_ontologies()
    )
    update_ontology_manager(om=toolbox.ontology_manager, llm_tool=toolbox.llm)


def create_agent_graph(tools: ToolBox) -> CompiledStateGraph:
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)

    # Create nodes with partial application of tools
    select_ontology_tuple = add_counter(
        partial(create_ontology_selector, tools=tools), WorkflowNode.SELECT_ONTOLOGY
    )
    render_ontology_tuple = add_counter(
        partial(create_onto_triples_renderer, tools=tools),
        WorkflowNode.TEXT_TO_ONTOLOGY,
    )
    render_facts_tuple = add_counter(
        partial(create_facts_renderer, tools=tools), WorkflowNode.TEXT_TO_FACTS
    )
    criticise_ontology_tuple = add_counter(
        partial(create_ontology_critic, tools=tools), WorkflowNode.CRITICISE_ONTOLOGY
    )
    criticise_facts_tuple = add_counter(
        partial(create_facts_critic, tools=tools), WorkflowNode.CRITICISE_FACTS
    )
    sublimate_ontology_tuple = add_counter(
        partial(create_ontology_sublimator, tools=tools),
        WorkflowNode.SUBLIMATE_ONTOLOGY,
    )
    save_kg_tuple = add_counter(
        partial(create_kg_saver, tools=tools), WorkflowNode.SAVE_KG
    )

    # Add nodes using string values
    workflow.add_node(*select_ontology_tuple)
    workflow.add_node(*render_ontology_tuple)
    workflow.add_node(*render_facts_tuple)
    workflow.add_node(*sublimate_ontology_tuple)
    workflow.add_node(*criticise_ontology_tuple)
    workflow.add_node(*criticise_facts_tuple)
    workflow.add_node(*save_kg_tuple)

    # Standard edges using string values
    workflow.add_edge(START, WorkflowNode.SELECT_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SELECT_ONTOLOGY, WorkflowNode.TEXT_TO_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SUBLIMATE_ONTOLOGY, WorkflowNode.CRITICISE_FACTS)
    workflow.add_edge(WorkflowNode.SAVE_KG, END)

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
            Status.SUCCESS: WorkflowNode.SAVE_KG,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    return workflow.compile()


def add_conditional_with_visit_counter_logic(
    workflow: StateGraph,
    current_node: WorkflowNode,
    mapping: dict[Status, WorkflowNode],
):
    def route(state: AgentState) -> Status:
        # Initialize visit count if not exists

        logger.info(f"Current node_visits state: {state.node_visits}")
        logger.info(
            f"Visiting {current_node} (visit {state.node_visits[current_node]}/{state.max_visits})"
        )

        if state.status == Status.SUCCESS:
            state.clear_failure()
            return state.status

        if state.node_visits[current_node] > state.max_visits:
            logger.error(f"Maximum visits exceeded for {current_node}")
            state.set_failure(current_node, "Maximum visits exceeded")
            return Status.SUCCESS
        else:
            return Status.FAILED

    workflow.add_conditional_edges(current_node, route, mapping)
