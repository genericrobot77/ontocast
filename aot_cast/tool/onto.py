from aot_cast.onto import BasePydanticModel


class Tool(BasePydanticModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
