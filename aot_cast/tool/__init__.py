from aot_cast.agent.get_ontology_summary import render_ontology_summary
from aot_cast.onto import Ontology
from .llm import LLMTool
from .ontology_manager import OntologyManager
from .onto import Tool
from .triple_manager import TripleStoreManager, FilesystemTripleStoreManager
from .converter import Converter
from .chunker import ChunkerTool
from .toolbox import ToolBox

__all__ = [
    "LLMTool",
    "OntologyManager",
    "TripleStoreManager",
    "FilesystemTripleStoreManager",
    "Converter",
    "ChunkerTool",
    "Tool",
    "ToolBox",
]


def update_ontology_properties(o: Ontology, llm_tool: LLMTool):
    props = render_ontology_summary(o.graph, llm_tool)
    o.set_properties(**props.model_dump())


def update_ontology_manager(om: OntologyManager, llm_tool: LLMTool):
    for o in om.ontologies:
        update_ontology_properties(o, llm_tool)


def init_toolbox(toolbox: ToolBox):
    toolbox.ontology_manager.ontologies = (
        toolbox.triple_store_manager.fetch_ontologies()
    )
    update_ontology_manager(om=toolbox.ontology_manager, llm_tool=toolbox.llm)
