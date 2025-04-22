from src.tools import TripleStoreManager, OntologyManager
from src.onto import ToolType


def create_ontology_manager_setter(tools):
    def set_ontologies(self, tsm: TripleStoreManager):
        tsm: TripleStoreManager = tools[ToolType.TRIPLE_STORE]
        om_tool: OntologyManager = tools[ToolType.ONTOLOGY_MANAGER]
        om_tool.ontologies = tsm.fetch_ontologies()

    return set_ontologies
