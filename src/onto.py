from pydantic import BaseModel, Field
from rdflib import Graph
from typing import Optional
import logging
import pathlib
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from typing import Any

from enum import StrEnum

logger = logging.getLogger(__name__)


class Status(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class RDFGraph(Graph):
    """Subclass to attach schema support for Pydantic."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, handler: GetCoreSchemaHandler):
        return core_schema.union_schema(
            [
                # Allow direct Graph instances
                core_schema.is_instance_schema(cls),
                # Allow string conversion
                core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_plain_validator_function(
                            cls._from_turtle_str
                        ),
                    ]
                ),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._to_turtle_str,
                info_arg=False,
                return_schema=core_schema.str_schema(),
            ),
        )

    @classmethod
    def _from_turtle_str(cls, turtle_str: str) -> "RDFGraph":
        turtle_str = bytes(turtle_str, "utf-8").decode("unicode_escape")
        g = cls()
        g.parse(data=turtle_str, format="turtle")
        return g

    @staticmethod
    def _to_turtle_str(g: Any) -> str:
        return g.serialize(format="turtle")

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        return instance


class OntologySummary(BaseModel):
    short_name: str = Field(description="A short name (identifier) for the ontology")
    title: str = Field(description="The name of the ontology")
    uri: str = Field(description="URI of the current ontology")
    description: str = Field(
        description="A consise description (3-4 sentences) of the ontology (domain, purpose, applicability, etc.)"
    )


class OntologySelector(BaseModel):
    short_name: Optional[str] = Field(
        description="A short name (identifier) for the ontology that could be used to represent the domain of the document, None if no ontology is suitable"
    )
    present: bool = Field(
        description="Whether an ontology that could represent the domain of the document is present in the list of ontologies"
    )


class TriplesProjection(BaseModel):
    semantic_graph: RDFGraph = Field(
        default_factory=RDFGraph,
        description="Semantic triples representing the document in turtle (ttl) format.",
    )
    ontology_relevance_score: Optional[float] = Field(
        description="The perceived score of how relevant the provided ontology is to the document (between 0 and 1)? 0 if ontology is not relevant (or not provided), 1 if ontology is fully relevant."
    )
    triples_generation_score: Optional[float] = Field(
        description="The perceived score of how well the triples generation task was performed (between 0 and 1)? 0 if the triples generation failed, 1 if the triples generation was perfect."
    )


class OntologyUpdateCritique(BaseModel):
    ontology_update_success: bool = Field(
        description="True if the ontology update was performed successfully, False otherwise"
    )
    ontology_update_critique_comment: Optional[str] = Field(
        description="A consise explanation (3-4 sentences) of why the ontology update is not satisfactory"
    )


class KGUpdateCritique(BaseModel):
    kg_update_success: bool = Field(
        description="True if the knowledge graph update was performed successfully, False otherwise"
    )
    kg_update_critique_comment: Optional[str] = Field(
        description="A consise explanation (3-4 sentences) of why the knowledge graph update is not satisfactory"
    )


class Ontology(BaseModel):
    """
    A Pydantic model representing an ontology with its RDF graph and description.

    Attributes:
        graph (Graph): The RDF graph containing the ontology data
        description (str): A human-readable description of the ontology
        name (Optional[str]): Optional name for the ontology
        version (Optional[str]): Optional version information
    """

    graph: RDFGraph = Field(default_factory=RDFGraph)
    description: str = Field(
        ..., description="Human-readable description of the ontology"
    )
    title: str = Field(..., description="Name of the ontology")
    short_name: str = Field(
        ..., description="A short name (identifier) for the ontology"
    )
    version: Optional[str] = Field(None, description="Version of the ontology")
    uri: Optional[str] = Field(None, description="URI of the ontology")

    class Config:
        arbitrary_types_allowed = True

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
        graph: RDFGraph = RDFGraph()
        graph.parse(file_path, format=format)
        ontology_str = graph.serialize(format=format)
        summary = get_ontology_summary(ontology_str)

        return cls(graph=graph, **summary.model_dump(), **kwargs)


class AgentState(BaseModel):
    """State for the ontology-based knowledge graph agent."""

    input_text: Optional[str] = None
    current_ontology_name: Optional[str] = None
    ontologies: list[Ontology] = []
    current_graph: Optional[RDFGraph] = Field(
        default_factory=RDFGraph, description="RDF knowledge graph"
    )
    ontology_modified: bool = False
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    ontology_addendum: Optional[RDFGraph] = Field(
        default_factory=RDFGraph, description="RDF triples to add to the ontology"
    )
    graph_facts: Optional[RDFGraph] = Field(
        default_factory=RDFGraph,
        description="RDF triples representing the facts from the current document",
    )
    status: Status = Status.SUCCESS
    node_visits: dict[str, int] = Field(
        default_factory=dict, description="Number of visits per node"
    )
    max_visits: int = Field(
        default=3, description="Maximum number of visits allowed per node"
    )

    class Config:
        arbitrary_types_allowed = True

    def set_failure(self, stage: str, reason: str) -> None:
        """
        Set failure state with stage and reason.

        Args:
            stage: The stage where the failure occurred
            reason: The reason for the failure
        """
        self.failure_stage = stage
        self.failure_reason = reason
        self.status = Status.FAILED

    def clear_failure(self) -> None:
        """Clear failure state and set status to success."""
        self.failure_stage = None
        self.failure_reason = None
        self.status = Status.SUCCESS

    def __init__(self, ontology_path: Optional[str] = None, **data):
        super().__init__(**data)
        if ontology_path is not None:
            for fname in pathlib.Path(ontology_path).glob("*.ttl"):
                try:
                    ontology = Ontology.from_file(fname)
                    self.ontologies.append(ontology)
                except Exception as e:
                    logging.error(f"Failed to load ontology {fname}: {str(e)}")

    @property
    def current_ontology(self) -> Ontology:
        if self.current_ontology_name is None:
            raise ValueError("No ontology selected")
        return next(
            o for o in self.ontologies if o.short_name == self.current_ontology_name
        )

    @property
    def ontology_names(self) -> list[str]:
        return [o.short_name for o in self.ontologies]

    def serialize(self, file_path: str | pathlib.Path) -> None:
        """
        Serialize the state to a JSON file.

        Args:
            file_path (Union[str, pathlib.Path]): Path to save the JSON file
        """
        state_json = self.model_dump_json(indent=4)
        if isinstance(file_path, str):
            file_path = pathlib.Path(file_path)
        file_path.write_text(state_json)

    @classmethod
    def load(cls, file_path: str | pathlib.Path) -> "AgentState":
        """
        Load state from a JSON file.

        Args:
            file_path (Union[str, pathlib.Path]): Path to the JSON file

        Returns:
            AgentState: The loaded state
        """
        if isinstance(file_path, str):
            file_path = pathlib.Path(file_path)
        state_json = file_path.read_text()
        return cls.model_validate_json(state_json)


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
