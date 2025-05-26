from src.onto import AgentState
from src.tools import ToolBox
from src.util import get_document_hash


def create_kg_saver(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that saves the knowledge graph."""
    tsm_tool = tools.triple_store_manager
    if state.graph_facts is not None:
        # Generate document hash
        doc_hash = get_document_hash(state.input_text)
        # Extract ontology extension from IRI
        ontology_ext = state.current_ontology.iri.split("/")[-1].split("#")[0]
        if not ontology_ext:
            ontology_ext = "default"

        tsm_tool.serialize_triples(
            state.current_ontology.graph, fname=f"onotology_{ontology_ext}_{doc_hash}"
        )
        tsm_tool.serialize_triples(
            state.graph_facts, fname=f"facts_{ontology_ext}_{doc_hash}"
        )

    return state
