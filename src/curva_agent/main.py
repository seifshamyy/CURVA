"""FastAPI application entry point."""
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException
from curva_agent import __version__
from curva_agent.config import get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.deps import get_curva_client, get_logs_repo, get_orchestrator, get_session_repo, get_taxonomy_repo, require_api_key
from curva_agent.observability.logging import configure_logging, get_logger
from curva_agent.observability.rate_limit import SlidingWindowRateLimiter
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest, AgentQueryResponse
from curva_agent.supabase_client.logs import AgentLogRow, AgentLogsRepository
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow
from curva_agent.supabase_client.taxonomy import TaxonomyRepository
from curva_agent.sync.taxonomy import sync_taxonomy

_session_limiter: SlidingWindowRateLimiter | None = None


def _get_session_limiter() -> SlidingWindowRateLimiter:
    global _session_limiter
    if _session_limiter is None:
        s = get_settings()
        _session_limiter = SlidingWindowRateLimiter(
            max_events=s.session_rate_limit_per_min, window_seconds=60.0
        )
    return _session_limiter


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("startup")
    log.info("service_starting", version=__version__, model=settings.llm_model)
    yield
    log.info("service_stopping")


app = FastAPI(title="Curva CS Agent", version=__version__, lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "curva-cs-agent", "version": __version__}


@app.post("/admin/sync-taxonomy", dependencies=[Depends(require_api_key)])
async def admin_sync_taxonomy(
    curva: CurvaClient = Depends(get_curva_client),
    repo: TaxonomyRepository = Depends(get_taxonomy_repo),
) -> dict:
    log = get_logger("admin.sync")
    started_at = datetime.now(timezone.utc).isoformat()
    log.info("sync_taxonomy_started", started_at=started_at)
    try:
        result = await sync_taxonomy(curva=curva, repo=repo)
    finally:
        await curva.aclose()
    log.info("sync_taxonomy_finished", ok=result.ok, counts=result.counts, error=result.error)
    return {"ok": result.ok, "counts": result.counts, "error": result.error, "started_at": started_at}


@app.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    dependencies=[Depends(require_api_key)],
)
async def agent_query(
    req: AgentQueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    sessions: SessionRepository = Depends(get_session_repo),
    logs: AgentLogsRepository = Depends(get_logs_repo),
) -> AgentQueryResponse:
    log = get_logger("agent_query").bind(session_id=req.session_id, locale=req.locale)
    log.info("turn_started", message_len=len(req.user_message))

    if not await _get_session_limiter().try_acquire(req.session_id):
        log.warning("session_rate_limited")
        raise HTTPException(status_code=429, detail="too many turns; slow down")

    started = time.perf_counter()
    ok = True
    error: str | None = None
    response: AgentQueryResponse | None = None
    next_state = None
    try:
        existing = await sessions.load(req.session_id)
        session_context = None
        if existing is not None:
            session_context = {
                "focus_product_ids": existing.focus_product_ids,
                "conversation_summary": existing.conversation_summary,
                "last_filters": existing.last_filters,
            }
        response, next_state = await orch.handle(req, session_context=session_context)
        await sessions.save(SessionRow(
            session_id=req.session_id,
            locale=req.locale,
            customer_name=(req.metadata.customer_name if req.metadata else None),
            focus_product_ids=next_state.focus_product_ids,
            last_filters=next_state.last_filters,
            conversation_summary=next_state.conversation_summary,
        ))
    except Exception as e:  # noqa: BLE001
        ok = False
        error = f"{type(e).__name__}: {e}"
        log.exception("turn_failed")
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            d = response.diagnostics if response and response.diagnostics else None
            await logs.write(AgentLogRow(
                session_id=req.session_id,
                user_message=req.user_message,
                reply_text=(response.reply_text if response else None),
                intent=(response.intent if response else None),
                tool_calls=(d.tool_calls_detail if d else []),
                product_ids=[p.id for p in (response.products if response else [])],
                model=(d.model if d else None),
                prompt_tokens=(d.prompt_tokens if d else 0),
                completion_tokens=(d.completion_tokens if d else 0),
                cached_tokens=(d.cached_tokens if d else 0),
                latency_ms=latency_ms,
                ok=ok,
                error=error,
            ))
        except Exception as logerr:  # noqa: BLE001
            log.warning("log_write_failed", error=str(logerr))

    log.info(
        "turn_finished",
        intent=response.intent if response else None,
        tool_calls=response.diagnostics.tool_calls if response and response.diagnostics else 0,
        latency_ms=latency_ms,
    )
    return response  # type: ignore[return-value]