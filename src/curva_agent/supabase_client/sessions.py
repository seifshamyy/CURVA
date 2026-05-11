"""Session memory repository."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class SessionRow:
    session_id: str
    locale: str = "ar"
    customer_name: str | None = None
    focus_product_ids: list[int] = field(default_factory=list)
    last_filters: dict[str, Any] | None = None
    conversation_summary: str = ""
    turn_count: int = 0


class _SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


class SessionRepository:
    TABLE = "agent_sessions"

    def __init__(self, client: _SupabaseLike) -> None:
        self._c = client

    async def load(self, session_id: str) -> SessionRow | None:
        r = await self._c.table(self.TABLE).select("*").eq("session_id", session_id).maybe_single().execute()
        if not getattr(r, "data", None):
            return None
        data = r.data
        return SessionRow(
            session_id=data["session_id"],
            locale=data.get("locale", "ar"),
            customer_name=data.get("customer_name"),
            focus_product_ids=data.get("focus_product_ids") or [],
            last_filters=data.get("last_filters"),
            conversation_summary=data.get("conversation_summary") or "",
            turn_count=data.get("turn_count") or 0,
        )

    async def save(self, row: SessionRow) -> None:
        existing = await self.load(row.session_id)
        new_turn_count = (existing.turn_count + 1) if existing else max(row.turn_count, 1)
        now = datetime.now(timezone.utc).isoformat()
        payload = asdict(row)
        payload["turn_count"] = new_turn_count
        payload["updated_at"] = now
        payload["last_active_at"] = now
        if existing is None:
            payload["created_at"] = now
        await self._c.table(self.TABLE).upsert(payload, on_conflict="session_id").execute()