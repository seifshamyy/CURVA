"""Append-only operational log of every agent turn."""
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class AgentLogRow:
    session_id: str
    user_message: str
    reply_text: str | None
    intent: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    product_ids: list[int] = field(default_factory=list)
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    ok: bool = True
    error: str | None = None


class _SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


class AgentLogsRepository:
    TABLE = "agent_logs"

    def __init__(self, client: _SupabaseLike) -> None:
        self._c = client

    async def write(self, row: AgentLogRow) -> None:
        await self._c.table(self.TABLE).insert(asdict(row)).execute()