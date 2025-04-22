from src.nodes.get_ontology_summary import render_summary
from src.onto import OntologyProperites


def test_extract_metadata(test_ontology, llm_tool):
    summary = render_summary(test_ontology, llm_tool)

    # Validate output
    assert isinstance(summary, OntologyProperites)
    assert "test" in summary.title.lower() and "ontology" in summary.title.lower()
    assert "test" in summary.description.lower()
