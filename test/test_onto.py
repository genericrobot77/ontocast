from src.onto import get_ontology_summary
from src.onto import OntologyProperites


def test_extract_metadata(test_ontology):
    summary = get_ontology_summary(test_ontology)

    # Validate output
    assert isinstance(summary, OntologyProperites)
    assert "test" in summary.title.lower() and "ontology" in summary.title.lower()
    assert "test" in summary.description.lower()
