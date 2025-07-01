from ontocast.toolbox import update_ontology_manager


def test_setup_onto(om_tool, tsm_tool, llm_tool):
    om_tool.ontologies = tsm_tool.fetch_ontologies()
    assert len(om_tool.ontologies) == 2
    update_ontology_manager(om=om_tool, llm_tool=llm_tool)
    assert "court" in om_tool.ontologies[0].title.lower()
    assert "crim" in om_tool.ontologies[0].description.lower()
    assert om_tool.ontologies[0].version == "3.0"
    assert om_tool.ontologies[1].version == "1.0"
