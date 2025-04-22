from rdflib import Namespace
from src.config import CURRENT_NS_IRI
from src.onto import AgentState, FailureStages, RDFGraph, ToolType


def _sublimate_ontology(state: AgentState):
    query_ontology = f"""
    PREFIX cd: <{CURRENT_NS_IRI}>
    
    SELECT ?s ?p ?o
    WHERE {{
    ?s ?p ?o .
    FILTER (
        !(
            STRSTARTS(STR(?s), STR(cd:)) ||
            STRSTARTS(STR(?p), STR(cd:)) ||
            (isIRI(?o) && STRSTARTS(STR(?o), STR(cd:)))
        )
    )
    }}
    """
    results = state.graph_facts.query(query_ontology)

    graph_onto_addendum = RDFGraph()

    # Add filtered triples to the new graph
    for s, p, o in results:
        graph_onto_addendum.add((s, p, o))

    query_facts = f"""
        PREFIX cd: <{CURRENT_NS_IRI}>

        SELECT ?s ?p ?o
        WHERE {{
        ?s ?p ?o .
        FILTER (
            STRSTARTS(STR(?s), STR(cd:)) ||
            STRSTARTS(STR(?p), STR(cd:)) ||
            (isIRI(?o) && STRSTARTS(STR(?o), STR(cd:)))
        )
        }}
    """

    graph_facts_pure = RDFGraph()

    results = state.graph_facts.query(query_facts)

    # Add filtered triples to the new graph
    for s, p, o in results:
        graph_facts_pure.add((s, p, o))

    return graph_onto_addendum, graph_facts_pure


def create_ontology_sublimator(tools):
    def _sublimator(state: AgentState) -> AgentState:
        """Separate ontology from facts"""

        om_tool = tools[ToolType.ONTOLOGY_MANAGER]
        try:
            graph_onto_addendum, graph_facts = _sublimate_ontology(state=state)

            ns_prefix_current_ontology = [
                p
                for p, ns in state.current_ontology.graph.namespaces()
                if str(ns) == state.current_ontology.iri
            ]

            graph_onto_addendum.bind(
                ns_prefix_current_ontology[0], Namespace(state.current_ontology.iri)
            )
            graph_facts.bind(
                ns_prefix_current_ontology[0], Namespace(state.current_ontology.iri)
            )

            om_tool.update_ontology(
                state.current_ontology.short_name, graph_onto_addendum
            )
            state.graph_facts = graph_facts
            state.clear_failure()
        except Exception as e:
            state.set_failure(
                FailureStages.FAILED_AT_SUBLIMATE_ONTOLOGY,
                str(e),
            )

        return state

    return _sublimator
