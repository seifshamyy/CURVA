"""List physical store branches."""
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    BranchInfo,
    ListBranchesInput,
    ListBranchesOutput,
)
from curva_agent.tools.base import Tool


class ListBranchesTool(Tool[ListBranchesInput, ListBranchesOutput]):
    name = "list_branches"
    description = (
        "List Curva physical store branches with phone numbers. Use when "
        "customer asks about pickup, store locations, or contact phones."
    )
    input_model = ListBranchesInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: ListBranchesInput, *, locale: str = "ar") -> ListBranchesOutput:
        key = f"list_branches:{locale}"

        async def load() -> ListBranchesOutput:
            r = await self._curva.get_branches(locale=locale)
            return ListBranchesOutput(
                branches=[BranchInfo(id=b.id, name=b.name, phones=b.phones) for b in r.data]
            )

        return await self._cache.get_or_load(key, load)