from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI


class LLMTool:
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
        self._llm = None

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = ChatOpenAI(model=self.model, temperature=self.temperature)
        return self._llm

    def get_parser(self, pydantic_object) -> PydanticOutputParser:
        return PydanticOutputParser(pydantic_object=pydantic_object)
