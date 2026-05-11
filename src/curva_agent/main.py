"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from curva_agent import __version__
from curva_agent.config import get_settings
from curva_agent.observability.logging import configure_logging, get_logger


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