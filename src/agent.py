import logging

from langgraph.graph import END, StateGraph, START
from langgraph.graph.state import CompiledStateGraph


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


def handle_visits(state: AgentState, node_name: str) -> tuple[AgentState, str]:
    """
    Handle visit counting for a node.

    Args:
        state: The current agent state
        node_name: The name of the node being visited

    Returns:
        tuple[AgentState, str]: Updated state and next node to execute
    """
    # Initialize visit count for this node if not exists
    if node_name not in state.node_visits:
        state.node_visits[node_name] = 0

    # Increment visit count
    state.node_visits[node_name] += 1
    logger.info(
        f"Visiting {node_name} (visit {state.node_visits[node_name]}/{state.max_visits})"
    )

    # Check if we've exceeded max visits
    if state.node_visits[node_name] > state.max_visits:
        logger.error(f"Maximum visits exceeded for {node_name}")
        state.set_failure(node_name, "Maximum visits exceeded")
        return state, END

    return state, node_name


def create_visit_route(success_node: WorkflowNode, current_node: WorkflowNode):
    """
    Create a route function with visit counting.

    Args:
        success_node: Node to go to on success
        current_node: Current node being visited

    Returns:
        A function that handles routing with visit counting
    """

    def route(state: AgentState) -> str:
        if state.status == Status.SUCCESS:
            state.clear_failure()  # Clear any previous failure state
            return success_node
        else:
            return handle_visits(state, current_node)[1]

    return route


def project_text_to_ontology_route(state: AgentState) -> str:
    """Route function for text to triples node with visit counting."""
    return create_visit_route(
        WorkflowNode.CRITICISE_ONTOLOGY, WorkflowNode.TEXT_TO_ONTOLOGY
    )(state)


def criticise_ontology_route(state: AgentState) -> str:
    """Route function for sublimate ontology node with visit counting."""
    return create_visit_route(
        WorkflowNode.TEXT_TO_FACTS, WorkflowNode.TEXT_TO_ONTOLOGY
    )(state)


def project_text_facts_route(state: AgentState) -> str:
    """Route function for criticise ontology update node with visit counting."""
    return create_visit_route(
        WorkflowNode.SUBLIMATE_ONTOLOGY, WorkflowNode.TEXT_TO_FACTS
    )(state)


def criticise_facts_route(state: AgentState) -> str:
    """Route function for criticise KG node with visit counting."""
    return create_visit_route(WorkflowNode.SAVE_KG, WorkflowNode.TEXT_TO_FACTS)(state)


def create_agent_graph(tools: ToolBox) -> CompiledStateGraph:
    """Create the agent workflow graph."""
    workflow = StateGraph(AgentState)

    select_ontology_node = create_ontology_selector(tools)
    render_ontology_triples = create_onto_triples_renderer(tools)
    render_facts_triples = create_facts_renderer(tools)
    criticise_ontology_update = create_ontology_critic(tools)
    criticise_facts = create_facts_critic(tools)
    sublimate_ontology = create_ontology_sublimator(tools)
    save_kg = create_kg_saver(tools)

    workflow.add_node(WorkflowNode.SELECT_ONTOLOGY, select_ontology_node)
    workflow.add_node(WorkflowNode.TEXT_TO_ONTOLOGY, render_ontology_triples)
    workflow.add_node(WorkflowNode.TEXT_TO_FACTS, render_facts_triples)

    workflow.add_node(WorkflowNode.SUBLIMATE_ONTOLOGY, sublimate_ontology)
    workflow.add_node(WorkflowNode.CRITICISE_ONTOLOGY, criticise_ontology_update)
    workflow.add_node(WorkflowNode.CRITICISE_FACTS, criticise_facts)
    workflow.add_node(WorkflowNode.SAVE_KG, save_kg)

    # Standard edges
    workflow.add_edge(START, WorkflowNode.SELECT_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SELECT_ONTOLOGY, WorkflowNode.TEXT_TO_ONTOLOGY)
    workflow.add_edge(WorkflowNode.SUBLIMATE_ONTOLOGY, WorkflowNode.CRITICISE_FACTS)

    workflow.add_edge(WorkflowNode.SAVE_KG, END)

    workflow.add_conditional_edges(
        WorkflowNode.TEXT_TO_ONTOLOGY,
        project_text_to_ontology_route,
        {
            Status.SUCCESS: WorkflowNode.CRITICISE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.CRITICISE_ONTOLOGY,
        criticise_ontology_route,
        {
            Status.SUCCESS: WorkflowNode.TEXT_TO_FACTS,
            Status.FAILED: WorkflowNode.TEXT_TO_ONTOLOGY,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.TEXT_TO_FACTS,
        project_text_facts_route,
        {
            Status.SUCCESS: WorkflowNode.SUBLIMATE_ONTOLOGY,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    workflow.add_conditional_edges(
        WorkflowNode.CRITICISE_FACTS,
        criticise_facts_route,
        {
            Status.SUCCESS: WorkflowNode.SAVE_KG,
            Status.FAILED: WorkflowNode.TEXT_TO_FACTS,
        },
    )

    return workflow.compile()
