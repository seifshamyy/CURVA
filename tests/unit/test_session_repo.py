from typing import Any
import pytest
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow


class StubTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filter: tuple | None = None

    def select(self, _cols: str = "*"):
        return self

    def eq(self, col: str, val: Any):
        self._filter = (col, val)
        return self

    def upsert(self, payload: dict, on_conflict: str = "session_id"):
        self.store.setdefault(self.name, {})[payload["session_id"]] = payload
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        if self._filter is not None:
            col, val = self._filter
            row = self.store.get(self.name, {}).get(val) if col == "session_id" else None
            return type("R", (), {"data": row})()
        return type("R", (), {"data": list(self.store.get(self.name, {}).values())})()


class StubSupabase:
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}

    def table(self, name: str) -> StubTable:
        return StubTable(self.store, name)


@pytest.mark.asyncio
async def test_load_returns_none_for_missing_session():
    repo = SessionRepository(StubSupabase())
    assert await repo.load("nonexistent") is None


@pytest.mark.asyncio
async def test_save_then_load_round_trip():
    sup = StubSupabase()
    repo = SessionRepository(sup)
    row = SessionRow(
        session_id="20100",
        locale="ar",
        customer_name="Ahmed",
        focus_product_ids=[10307],
        last_filters={"club_id": 26},
        conversation_summary="asked Zamalek",
        turn_count=1,
    )
    await repo.save(row)
    loaded = await repo.load("20100")
    assert loaded is not None
    assert loaded.session_id == "20100"
    assert loaded.focus_product_ids == [10307]
    assert loaded.last_filters == {"club_id": 26}
    assert loaded.turn_count == 1


@pytest.mark.asyncio
async def test_save_increments_turn_count_for_existing_session():
    sup = StubSupabase()
    repo = SessionRepository(sup)
    await repo.save(SessionRow(session_id="x", locale="ar"))
    await repo.save(SessionRow(session_id="x", locale="ar"))
    loaded = await repo.load("x")
    assert loaded.turn_count == 2