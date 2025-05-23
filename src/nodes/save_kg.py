from src.onto import AgentState
from src.tools import ToolBox
from src.util import get_document_hash


def create_kg_saver(tools: ToolBox):
    """Create a node that saves the knowledge graph."""

    def _saver(
        state: AgentState,
    ) -> AgentState:
        """Update the knowledge graph with the new facts"""
        tsm_tool = tools.tsm_tool
        if state.graph_facts is not None:
            # Generate document hash
            doc_hash = get_document_hash(state.input_text)
            # Extract ontology extension from IRI
            ontology_ext = state.current_ontology.iri.split("/")[-1].split("#")[0]
            if not ontology_ext:
                ontology_ext = "default"
            # Create filename with hash
            tsm_tool.serialize_triples(
                state.graph_facts, f"kg_{ontology_ext}_{doc_hash}"
            )
        return state

    return _saver
