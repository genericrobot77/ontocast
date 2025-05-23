from pydantic import BaseModel
from typing import Optional
import pathlib
from src.tools import (
    FilesystemTripleStoreManager,
    OntologyManager,
    LLMTool,
    Converter,
    ChunkerTool,
)


class ToolBox(BaseModel):
    llm_tool: Optional[LLMTool] = None
    tsm_tool: Optional[FilesystemTripleStoreManager] = None
    om_tool: Optional[OntologyManager] = None
    converter_tool: Optional[Converter] = None
    chunker_tool: Optional[ChunkerTool] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        working_directory: pathlib.Path = kwargs.pop("working_directory")
        ontology_directory: Optional[pathlib.Path] = kwargs.pop("ontology_directory")
        model_name: str = kwargs.pop("model_name")
        temperature: float = kwargs.pop("temperature")

        self.llm_tool = LLMTool.create(model=model_name, temperature=temperature)
        self.tsm_tool = FilesystemTripleStoreManager(
            working_directory=working_directory, ontology_path=ontology_directory
        )
        self.om_tool = OntologyManager()
        self.converter_tool = Converter()
        self.chunker_tool = ChunkerTool()
