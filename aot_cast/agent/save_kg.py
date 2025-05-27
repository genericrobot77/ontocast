from aot_cast.onto import AgentState
from aot_cast.tools import ToolBox


def create_kg_saver(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that saves the knowledge graph."""
    tsm_tool = tools.triple_store_manager
    if state.graph_facts is not None:
        tsm_tool.serialize_ontology(state.current_ontology)

        tsm_tool.serialize_facts(state.graph_facts)

    return state
