from pydantic import BaseModel, Field
from rdflib import Graph
from typing import Optional
import logging
import pathlib


from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate


logger = logging.getLogger(__name__)


class OntologySummary(BaseModel):
    short_name: str = Field(description="A short name (identifier) for the ontology")
    title: str = Field(description="The name of the ontology")
    description: str = Field(
        description="A consise description (3-4 sentences) of the ontology (domain, purpose, applicability, etc.)"
    )


def get_ontology_summary(ontology_str: str) -> OntologySummary:
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Define the output parser
    parser = PydanticOutputParser(pydantic_object=OntologySummary)

    # Create the prompt template with format instructions
    prompt = PromptTemplate(
        template=(
            "Below is an ontology in Turtle format:\n\n"
            "{ontology_str}\n\n"
            "Read it and generate a name and a short description (3-4 sentences max) of the ontology.\n"
            "{format_instructions}"
        ),
        input_variables=["ontology_str"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    response = llm(prompt.format_prompt(ontology_str=ontology_str))

    return parser.parse(response.content)


class Ontology(BaseModel):
    """
    A Pydantic model representing an ontology with its RDF graph and description.

    Attributes:
        graph (Graph): The RDF graph containing the ontology data
        description (str): A human-readable description of the ontology
        name (Optional[str]): Optional name for the ontology
        version (Optional[str]): Optional version information
    """

    graph: Graph
    description: str = Field(
        ..., description="Human-readable description of the ontology"
    )
    title: str = Field(..., description="Name of the ontology")
    short_name: str = Field(
        ..., description="A short name (identifier) for the ontology"
    )
    version: Optional[str] = Field(None, description="Version of the ontology")

    class Config:
        arbitrary_types_allowed = (
            True  # This is needed to allow RDFlib Graph as a field type
        )

    def __str__(self) -> str:
        """Return a string representation of the ontology."""
        return (
            f"Ontology(name={self.title}, version={self.version})\n{self.description}"
        )

    def serialize(self, format: str = "turtle") -> str:
        """
        Serialize the ontology graph to a string in the specified format.

        Args:
            format (str): The format to serialize to (e.g., "turtle", "xml", "json-ld")

        Returns:
            str: The serialized graph
        """
        return self.graph.serialize(format=format)

    @classmethod
    def from_file(cls, file_path: pathlib.Path, format: str = "turtle", **kwargs):
        """
        Create an Ontology instance by loading a graph from a file.

        Args:
            file_path (str): Path to the ontology file
            description (str): Description of the ontology
            format (str): Format of the input file (default: "turtle")
            **kwargs: Additional arguments to pass to the constructor

        Returns:
            Ontology: A new Ontology instance
        """
        graph: Graph = Graph()
        graph.parse(file_path, format=format)
        ontology_str = graph.serialize(format=format)
        summary = get_ontology_summary(ontology_str)

        return cls(graph=graph, **summary.model_dump(), **kwargs)


class AgentState:
    """State for the ontology-based knowledge graph agent."""

    input_text: Optional[str] = None
    current_ontology_name: Optional[str] = None

    ontologies: list[Ontology] = []
    knowledge_graph: Optional[Graph] = None
    ontology_modified: bool = False

    def __init__(self, ontology_path: str):
        for fname in pathlib.Path(ontology_path).glob("*.ttl"):
            try:
                ontology = Ontology.from_file(
                    fname,
                )
                self.ontologies.append(ontology)
            except Exception as e:
                logging.error(f"Failed to load ontology {fname}: {str(e)}")

        self.knowledge_graph = Graph()
