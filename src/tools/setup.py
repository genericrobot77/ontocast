from src.tools import TripleStoreManager, OntologyManager, LLMTool
from src.onto import ToolType
from src.nodes.update_ontology_properties import update_ontology_manager


def setup_tools(tools):
    tsm: TripleStoreManager = tools[ToolType.TRIPLE_STORE]
    om_tool: OntologyManager = tools[ToolType.ONTOLOGY_MANAGER]
    llm_tool: LLMTool = tools[ToolType.LLM]
    om_tool.ontologies = tsm.fetch_ontologies()
    update_ontology_manager(om=om_tool, llm_tool=llm_tool)
