"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from curva_agent import __version__
from curva_agent.config import get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.deps import get_curva_client, get_orchestrator, get_taxonomy_repo, require_api_key
from curva_agent.observability.logging import configure_logging, get_logger
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest, AgentQueryResponse
from curva_agent.supabase_client.taxonomy import TaxonomyRepository
from curva_agent.sync.taxonomy import sync_taxonomy


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
) -> AgentQueryResponse:
    log = get_logger("agent_query").bind(session_id=req.session_id, locale=req.locale)
    log.info("turn_started", message_len=len(req.user_message))
    response, _next_state = await orch.handle(req, session_context=None)
    log.info("turn_finished", intent=response.intent, tool_calls=response.diagnostics.tool_calls if response.diagnostics else 0)
    return response