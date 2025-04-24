from src.onto import BasePydanticModel


class Tool(BasePydanticModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
