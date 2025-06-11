import logging

from ontocast.onto import AgentState
from ontocast.toolbox import ToolBox

logger = logging.getLogger(__name__)


def aggregate_serialize(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that saves the knowledge graph."""
    tsm_tool = tools.triple_store_manager

    aggregated_graph = tools.aggregator.aggregate_graphs(
        state.chunks_processed, state.doc_namespace
    )
    logger.info(
        f"chunks proc: {len(state.chunks_processed)}"
        f"facts graph: {len(aggregated_graph)} triples"
        f"onto graphL {state.current_ontology} triples"
    )
    tsm_tool.serialize_ontology(state.current_ontology)
    if len(aggregated_graph) > 0:
        tsm_tool.serialize_facts(aggregated_graph, spec=state.doc_namespace)

    return state
