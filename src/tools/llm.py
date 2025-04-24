from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from typing import Type, TypeVar, Any
from pydantic import BaseModel, Field
import asyncio
from typing import Optional
from .onto import Tool
# from langchain.tools import Tool

T = TypeVar("T", bound=BaseModel)


class LLMTool(Tool):
    model: str = Field(default="gpt-4o-mini")
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._llm = None

    @classmethod
    def create(cls, **kwargs):
        return asyncio.run(cls.acreate(**kwargs))

    @classmethod
    async def acreate(cls, **kwargs):
        self = cls.__new__(cls)
        self.__init__(**kwargs)
        await self.setup()
        return self

    async def setup(self):
        self._llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
        )

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.llm.invoke(*args, **kwds)

    @property
    def llm(self) -> BaseChatModel:
        """Access to the LangChain ChatOpenAI instance"""
        if self._llm is None:
            raise RuntimeError(
                "LLM resource not properly initialized. Call setup() first."
            )
        return self._llm

    def get_parser(self, pydantic_object: Type[T]) -> PydanticOutputParser:
        """Get a LangChain Pydantic parser for the given model"""
        return PydanticOutputParser(pydantic_object=pydantic_object)

    async def complete(self, prompt: str, **kwargs) -> Any:
        response = await self.llm.ainvoke(prompt)
        return response.content

    async def extract(self, prompt: str, output_schema: Type[T], **kwargs) -> T:
        """Extract structured data according to schema"""
        parser = self.get_parser(output_schema)
        format_instructions = parser.get_format_instructions()

        full_prompt = f"{prompt}\n\n{format_instructions}"
        response = await self.llm.ainvoke(full_prompt)

        return parser.parse(response.content)
