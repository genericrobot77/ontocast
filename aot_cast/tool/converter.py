from .onto import Tool
from docling.document_converter import DocumentConverter
from io import BytesIO
from typing import Union, Dict, Any
from docling.datamodel.base_models import (
    DocumentStream,
)


class Converter(Tool):
    supported_extensions: set[str] = {".pdf", ".ppt", ".pptx"}

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._converter = DocumentConverter()

    def __call__(self, file_input: Union[BytesIO, str]) -> Dict[str, Any]:
        """
        Convert a file to markdown text.

        Args:
            file_input: Either a BytesIO object or a string containing the file content

        Returns:
            Dict containing the converted text
        """
        if isinstance(file_input, BytesIO):
            ds = DocumentStream(name="doc", stream=file_input)
            result = self._converter.convert(ds)
            doc = result.document.export_to_markdown()
            return {"text": doc}
        else:
            # For non-BytesIO input (like plain text), return as is
            return {"text": file_input}
