from pydantic import BaseModel
from typing import Optional
import pathlib
from aot_cast.tool import (
    TripleStoreManager,
    FilesystemTripleStoreManager,
    OntologyManager,
    LLMTool,
    Converter,
    ChunkerTool,
)


class ToolBox(BaseModel):
    llm: Optional[LLMTool] = None
    triple_store_manager: Optional[TripleStoreManager] = None
    ontology_manager: Optional[OntologyManager] = None
    converter: Optional[Converter] = None
    chunker: Optional[ChunkerTool] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        working_directory: pathlib.Path = kwargs.pop("working_directory")
        ontology_directory: Optional[pathlib.Path] = kwargs.pop("ontology_directory")
        model_name: str = kwargs.pop("model_name")
        temperature: float = kwargs.pop("temperature")

        self.llm = LLMTool.create(model=model_name, temperature=temperature)
        self.triple_store_manager = FilesystemTripleStoreManager(
            working_directory=working_directory, ontology_path=ontology_directory
        )
        self.ontology_manager = OntologyManager()
        self.converter = Converter()
        self.chunker = ChunkerTool()
