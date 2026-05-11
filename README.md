# Curva CS Agent

WhatsApp customer service agent for [curvaegypt.com](https://curvaegypt.com).
Single FastAPI endpoint backed by Claude Sonnet 4.6 (via OpenRouter), Supabase,
and live upstream Curva API calls.

## Quick start

1. Copy `.env.example` → `.env` and fill in keys.
2. Start Supabase locally: `npx supabase start`
3. Apply migrations: `npx supabase db reset`
4. Run: `uvicorn curva_agent.main:app --reload --port 8000`
5. Seed taxonomy: `curl -sX POST -H "X-API-Key: $AGENT_API_KEY" http://localhost:8000/admin/sync-taxonomy`

## Endpoints

- `POST /agent/query` — primary agent endpoint (auth: `X-API-Key`)
- `POST /admin/sync-taxonomy` — manual taxonomy refresh (auth: `X-API-Key`)
- `GET /healthz` — liveness

## Tests

```bash
pytest -v
```

## Deploy

Single container. See `Dockerfile`. Deploy to Cloud Run or Fly.io. Required env
vars are in `.env.example`.

## Architecture

See [docs/superpowers/specs/2026-05-11-curva-cs-agent-design.md](docs/superpowers/specs/2026-05-11-curva-cs-agent-design.md).