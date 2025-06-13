"""Fact aggregation agent for OntoCast.

This module provides functionality for aggregating and serializing facts from
multiple chunks into a single RDF graph, handling entity and predicate
disambiguation.
"""

import logging

from ontocast.onto import AgentState
from ontocast.toolbox import ToolBox

logger = logging.getLogger(__name__)


def aggregate_serialize(state: AgentState, tools: ToolBox) -> AgentState:
    """Create a node that saves the knowledge graph."""
    tsm_tool = tools.triple_store_manager

    for c in state.chunks_processed:
        c.sanitize()

    state.aggregated_facts = tools.aggregator.aggregate_graphs(
        state.chunks_processed, state.doc_namespace
    )
    logger.info(
        f"chunks proc: {len(state.chunks_processed)}\n"
        f"facts graph: {len(state.aggregated_facts)} triples\n"
        f"onto graph {len(state.current_ontology.graph)} triples"
    )
    tsm_tool.serialize_ontology(state.current_ontology)
    if len(state.aggregated_facts) > 0:
        tsm_tool.serialize_facts(state.aggregated_facts, spec=state.doc_namespace)

    return state
