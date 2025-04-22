from src.tools import LLMTool, OntologyManager
from src.nodes.get_ontology_summary import render_summary
from src.onto import Ontology


def update_ontology_properties(o: Ontology, llm_tool: LLMTool):
    props = render_summary(o.graph, llm_tool)
    o.set_properties(**props.model_dump())


def update_ontology_manager(om: OntologyManager, llm_tool: LLMTool):
    for o in om.ontologies:
        update_ontology_properties(o, llm_tool)
