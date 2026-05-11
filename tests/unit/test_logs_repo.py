from typing import Any
import pytest
from curva_agent.supabase_client.logs import AgentLogsRepository, AgentLogRow


class StubTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name

    def insert(self, payload: dict):
        self._payload = payload
        return self

    async def execute(self):
        self.store.setdefault(self.name, []).append(self._payload)
        return type("R", (), {"data": [self._payload]})()


class StubSupabase:
    def __init__(self):
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> StubTable:
        return StubTable(self.store, name)


@pytest.mark.asyncio
async def test_write_log_row_inserts_into_table():
    sup = StubSupabase()
    repo = AgentLogsRepository(sup)
    await repo.write(AgentLogRow(
        session_id="20100",
        user_message="hi",
        reply_text="hello",
        intent="smalltalk",
        tool_calls=[{"name": "echo", "ok": True}],
        product_ids=[10307],
        model="anthropic/claude-sonnet-4.6",
        prompt_tokens=100, completion_tokens=20, cached_tokens=50,
        latency_ms=1200, ok=True, error=None,
    ))
    rows = sup.store["agent_logs"]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "20100"
    assert rows[0]["tool_calls"][0]["name"] == "echo"
    assert rows[0]["ok"] is True