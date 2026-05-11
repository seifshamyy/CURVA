"""Shared base class for tools.

Each tool encapsulates: input schema, output schema, a `run` coroutine,
and a `tool_spec()` that the LLM client uses to register the tool.
"""
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class Tool(ABC, Generic[I, O]):
    name: str = ""
    description: str = ""
    input_model: type[BaseModel]

    @abstractmethod
    async def run(self, args: I, *, locale: str = "ar") -> O: ...

    def tool_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }