from src.onto import (
    AgentState,
    RDFGraph,
    Status,
    ONTOLOGY_VOID_ID,
    DEFAULT_DOMAIN,
    ToolType,
)

from src.nodes import (
    create_ontology_selector,
    create_onto_triples_renderer,
    create_facts_renderer,
    create_facts_critic,
    create_ontology_critic,
    create_ontology_sublimator,
)
from src.tools import OntologyManager
from rdflib import URIRef, Literal
from packaging.version import Version
import pytest


def test_agent_state_json():
    state = AgentState()
    state.graph_facts = RDFGraph()
    state.graph_facts.add(
        (
            URIRef("http://example.com/subject"),
            URIRef("http://example.com/predicate"),
            Literal("object"),
        )
    )

    state_json = state.model_dump_json()

    loaded_state = AgentState.model_validate_json(state_json)

    assert isinstance(loaded_state.graph_facts, RDFGraph)


@pytest.mark.order(after="test_select_ontology")
def test_agent_text_to_ontology_fresh(
    agent_state_select_ontology: AgentState, apple_report: dict, tools
):
    """here no relevant ontology is present, we are trying to create a new one"""
    agent_state_select_ontology.input_text = apple_report["text"]

    render_ontology_triples = create_onto_triples_renderer(tools)
    agent_state = render_ontology_triples(agent_state_select_ontology)

    assert agent_state.ontology_addendum.iri is not None
    assert agent_state.ontology_addendum.title is not None
    assert agent_state.ontology_addendum.short_name is not None
    assert agent_state.ontology_addendum.description is not None
    assert agent_state.ontology_addendum.iri.startswith(DEFAULT_DOMAIN)
    assert len(agent_state.ontology_addendum.graph) > 0
    assert Version(agent_state.ontology_addendum.version) >= Version("0.0.0")
    agent_state.serialize("test/data/agent_state.onto.fresh.json")


@pytest.mark.order(after="test_agent_state")
def test_select_ontology(
    agent_state_init: AgentState,
    apple_report: dict,
    legal_report: dict,
    random_report: dict,
    tools,
    state_onto_selected_fname,
    state_onto_null_fname,
):
    select_ontology = create_ontology_selector(tools)

    agent_state_init.input_text = legal_report["text"]
    agent_state = select_ontology(agent_state_init)
    assert "fcaont" in agent_state.current_ontology.iri

    agent_state_init.input_text = apple_report["text"]
    agent_state = select_ontology(agent_state_init)
    assert "fsec" in agent_state.current_ontology.iri

    agent_state_init.serialize(state_onto_selected_fname)

    agent_state_init.input_text = random_report["text"]
    agent_state_init = select_ontology(agent_state_init)
    assert agent_state_init.current_ontology.short_name == ONTOLOGY_VOID_ID

    agent_state_init.serialize(state_onto_null_fname)


@pytest.mark.order(after="test_select_ontology")
def test_agent_text_to_ontology_critique_loop(
    agent_state_select_ontology: AgentState, apple_report: dict, tools, max_iter
):
    state = agent_state_select_ontology
    state.input_text = apple_report["text"]
    state.status = Status.FAILED

    k_init = 0
    if k_init > 0:
        state = AgentState.load(
            f"test/data/agent_state.onto.critique.loop.{k_init}.json"
        )

    criticise_ontology_update = create_ontology_critic(tools)
    render_ontology_triples = create_onto_triples_renderer(tools)

    k = k_init
    while state.status == Status.FAILED and k < k_init + max_iter:
        state = render_ontology_triples(state)
        assert state.ontology_addendum.iri is not None
        assert state.ontology_addendum.iri.startswith(DEFAULT_DOMAIN)
        assert len(state.ontology_addendum.graph) > 0

        state = criticise_ontology_update(state)
        print(
            len(state.current_ontology.graph),
            len(state.ontology_addendum.graph),
        )
        print(f"current version: {Version(state.ontology_addendum.version)}")
        print(f"success score: {state.success_score}")
        print(state.failure_reason)
        if state.status != Status.SUCCESS:
            state.serialize(f"test/data/agent_state.onto.critique.loop.{k}.json")
        k += 1
    state.status == Status.SUCCESS
    state.clear_failure()
    state.serialize("test/data/agent_state.onto.critique.success.json")


@pytest.mark.order(after="test_select_ontology")
def test_agent_text_to_ontology_null_critique_loop(
    agent_state_select_ontology_null: AgentState, apple_report: dict, tools, max_iter
):
    state = agent_state_select_ontology_null
    om_tool: OntologyManager = tools[ToolType.ONTOLOGY_MANAGER]
    om_tool.ontologies = []
    state.input_text = apple_report["text"]
    state.status = Status.FAILED

    k_init = 0
    if k_init > 0:
        state = AgentState.load(
            f"test/data/agent_state.onto.null.critique.loop.{k_init}.json"
        )

    criticise_ontology_update = create_ontology_critic(tools)
    render_ontology_triples = create_onto_triples_renderer(tools)

    k = k_init
    while state.status == Status.FAILED and k < k_init + max_iter:
        state = render_ontology_triples(state)
        assert state.ontology_addendum.iri is not None
        assert state.ontology_addendum.iri.startswith(DEFAULT_DOMAIN)
        assert len(state.ontology_addendum.graph) > 0

        state = criticise_ontology_update(state)
        print(
            len(state.current_ontology.graph),
            len(state.ontology_addendum.graph),
        )
        print(f"current version: {Version(state.ontology_addendum.version)}")
        print(f"success score: {state.success_score}")
        print(state.failure_reason)
        if state.status != Status.SUCCESS:
            state.serialize(f"test/data/agent_state.onto.null.critique.loop.{k}.json")
        k += 1
    state.status == Status.SUCCESS
    state.clear_failure()
    state.serialize("test/data/agent_state.onto.null.critique.success.json")


@pytest.mark.order(after="test_agent_text_to_ontology_null_critique_loop")
def test_agent_text_to_facts_critique_loop(
    agent_state_onto_critique_success: AgentState, apple_report: dict, tools, max_iter
):
    render_facts_triples = create_facts_renderer(tools)
    criticise_facts = create_facts_critic(tools)
    sublimate_ontology = create_ontology_sublimator(tools)

    agent_state = agent_state_onto_critique_success
    agent_state.input_text = apple_report["text"]
    agent_state.status = Status.FAILED

    k_init = 0
    if k_init > 0:
        agent_state = AgentState.load(
            f"test/data/agent_state.facts.critique.loop.{k_init}.json"
        )

    k = k_init
    while agent_state.status == Status.FAILED and k < k_init + max_iter:
        agent_state = render_facts_triples(agent_state)
        assert len(agent_state.graph_facts) > 0
        agent_state = sublimate_ontology(agent_state)
        agent_state = criticise_facts(agent_state)

        assert agent_state.success_score > 0

        if agent_state.status == Status.SUCCESS:
            agent_state.serialize("test/data/agent_state.facts.critique.success.json")
        else:
            agent_state.serialize(f"test/data/agent_state.facts.critique.loop.{k}.json")
        k += 1
    agent_state.status == Status.SUCCESS
    agent_state.clear_failure()
    agent_state.serialize("test/data/agent_state.facts.critique.success.json")


# def test_agent_text_to_facts(
#     agent_state_onto_critique_success: AgentState, apple_report: dict, tools
# ):
#     render_facts_triples = create_facts_renderer(tools)

#     agent_state_onto_critique_success.input_text = apple_report["text"]
#     agent_state = render_facts_triples(agent_state_onto_critique_success)

#     assert len(agent_state.graph_facts) > 0
#     # Verify that triples use the current ontology's namespace
#     current_ns = agent_state.current_ontology.iri
#     has_ns = False
#     for s, p, o in agent_state.graph_facts:
#         if (
#             str(s).startswith(current_ns)
#             or str(p).startswith(current_ns)
#             or str(o).startswith(current_ns)
#         ):
#             has_ns = True
#             break
#     assert has_ns, f"No triples found using namespace {current_ns}"

#     agent_state.serialize("test/data/agent_state.project_triples.json")


# def test_agent_state_sublimate_ontology():
#     agent_state = AgentState.load("test/data/agent_state.project_triples.json")
#     graph_onto_addendum, graph_facts_pure = _sublimate_ontology(agent_state)
#     assert len(agent_state.graph_facts) == len(graph_facts_pure) + len(
#         graph_onto_addendum
#     )


# def test_agent_state_sublimate_ontology_full(tools):
#     agent_state = AgentState.load("test/data/agent_state.project_triples.json")
#     sublimate_ontology = create_ontology_sublimator(tools)
#     agent_state = sublimate_ontology(agent_state)
#     assert len(agent_state.graph_facts) > 0
