# Curva CS Agent — Design Document

**Date:** 2026-05-11
**Status:** Approved (brainstorming complete; ready for implementation plan)
**Stack:** Python 3.12+, FastAPI, Supabase (Postgres + Edge Functions), Claude Sonnet 4.6 via OpenRouter

---

## 1. Purpose

A WhatsApp-driven customer service agent for **curvaegypt.com** — a football merchandise retailer with ~4,235 SKUs across 117 clubs/national teams, 76 brands, 7 categories, and 70 subcategories.

The agent is the first-line CS rep over WhatsApp Business API (fronted by n8n). It searches the catalog, answers product questions, sends product photos, checks availability across sizes/colors, and surfaces order intent for the client's downstream CRM. CRM integration is **out of scope** for this spec — handled by the client.

## 2. Goals

- **Tiny tool surface for the agent.** Maximum 1–3 endpoints exposed to n8n. Heavy lifting lives behind the endpoint, not in the agent's prompt.
- **Agent loop with multiple tool calls per user turn.** The orchestrator can call several tools in sequence and in parallel within one turn — e.g., resolve "Real Madrid kit M" → search → fetch detail → check stock → format.
- **Multiple searches per turn supported natively.** Comparison queries fan out parallel `search_products` calls in one assistant step.
- **Session memory** keyed by WhatsApp phone number. Customer says "do you have it in M?" three turns later and the agent knows what "it" is.
- **Deterministic-first search.** Use Curva's strong filter taxonomy (club, brand, season, category, subcategory, price) via LLM reasoning. Vector search is *not* the primary lane.
- **Bilingual.** Arabic primary, English secondary, both seamless. LLM resolves "أهلي" / "Al Ahly" / "ahly" → `club_id=25` natively.
- **Latency budget:** ~20–30s per turn is acceptable. Quality > speed.
- **Provider-flexible.** Sonnet 4.6 via OpenRouter at launch. Drop-in swap to GPT-5 via the same OpenRouter client behind a config flag.

## 3. Non-Goals

- Image embeddings / reverse image search via SigLip2 (deferred; schema reserved)
- Vector text embedding fallback (deferred; schema reserved)
- Order placement to Curva's API (no public auth flow; handoff to client CRM is downstream)
- Authentication for end users (WhatsApp + n8n handles that)
- Multi-tenant deployment — single client
- Admin UI (Supabase Studio is sufficient for now)

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     n8n (WhatsApp orchestration)                  │
└──────────────────────────┬────────────────────────────────────────┘
                           │ POST /agent/query
                           │ { session_id, user_message, locale, … }
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│         Agent Service — Python / FastAPI / asyncio                │
│         Deployed: Cloud Run or Fly.io (long-lived container)      │
│                                                                   │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │           MASTER ORCHESTRATOR (Sonnet 4.6 / OpenRouter)     │ │
│   │  • System prompt = role + cached taxonomy + tool catalog    │ │
│   │  • Anthropic prompt caching on the taxonomy block           │ │
│   │  • Tool-use loop until structured final response emitted    │ │
│   │  • Safety cap: 12 tool iterations                           │ │
│   └────┬───────────┬───────────┬───────────┬───────────┬───────┘ │
│        ▼           ▼           ▼           ▼           ▼          │
│   ┌────────┐ ┌─────────┐ ┌────────┐ ┌─────────┐ ┌─────────────┐ │
│   │search_ │ │ get_    │ │ get_   │ │ list_   │ │  Product    │ │
│   │products│ │ product │ │ offers │ │branches │ │ Synthesizer │ │
│   │        │ │         │ │        │ │         │ │ (sub-agent) │ │
│   └───┬────┘ └────┬────┘ └───┬────┘ └────┬────┘ └──────┬──────┘ │
│       │           │          │           │             │         │
│       └─────┬─────┴──────────┴───────────┘             │         │
│             │  In-memory LRU cache (10–24min TTL)      │         │
│             └──────────────────┬─────────────────────────┘         │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
        ┌────────────────────┐        ┌────────────────────────┐
        │  Curva API (live)  │        │   Supabase Postgres    │
        │  octane.curva...   │        │   • taxonomy           │
        │                    │        │   • agent_sessions     │
        │                    │        │   • agent_logs         │
        │                    │        │   • taxonomy_sync_runs │
        │                    │        │   • [embeddings*]      │
        └────────────────────┘        └──────────┬─────────────┘
                                                 │
                                      ┌──────────┴───────────┐
                                      │ Edge Function (weekly │
                                      │ cron): refresh        │
                                      │ taxonomy from upstream│
                                      └───────────────────────┘
                                      *reserved for future use
```

### 4.1 Agent Service (Python + FastAPI)

- Single container, async throughout (`asyncio` + `httpx.AsyncClient`)
- Deployed to Cloud Run or Fly.io. **Not** a Supabase Edge Function — needs a long-lived process for the in-memory LRU cache and to avoid cold starts on 20–30s agent loops.
- Endpoints:
  - `POST /agent/query` — primary agent endpoint (the only one n8n calls)
  - `GET /healthz` — liveness probe
  - `POST /admin/sync-taxonomy` — manual taxonomy refresh trigger (shared-secret auth)

### 4.2 Master Orchestrator

- **Model:** `anthropic/claude-sonnet-4.6` via OpenRouter
- **Client abstraction:** A small `LLMClient` interface so `anthropic/claude-sonnet-4.6` ↔ `openai/gpt-5` is a one-line swap.
- **System prompt structure (built per turn, with stable prefix for caching):**
  1. Role + voice (Curva CS rep, bilingual, friendly, accurate)
  2. **Cached block:** Full taxonomy snapshot (categories, subcategories, clubs, brands, seasons, branches) as compact JSON — wrapped in an Anthropic `cache_control` breakpoint
  3. Tool catalog + JSON schemas
  4. Response-format contract (final JSON the orchestrator emits)
  5. **Per-turn dynamic block (not cached):** session summary + recent conversation
- **Loop control:** Standard Anthropic tool-use loop. Orchestrator decides when it has enough data and emits its final structured response. Safety cap: **12 tool iterations** (configurable via env var).
- **Parallel tool calls:** Permitted. Anthropic's tool-use protocol allows multiple `tool_use` blocks per assistant turn — used for comparison queries (e.g., "Adidas vs Nike Real Madrid").
- **Streaming:** Disabled. n8n consumes a single JSON payload at the end of the loop.

### 4.3 Tools (deterministic — plain functions, no LLM)

| Tool | Upstream call | Purpose | Cache TTL |
|------|---------------|---------|-----------|
| `search_products(filters)` | `POST /products` | Filter-based catalog search | 10 min |
| `get_product(product_id)` | `GET /product/{id}` | Full detail incl. sizes/colors/stock/images | 15 min |
| `get_offers(page, limit)` | `GET /offers?page=…` | Currently discounted products | 10 min |
| `list_branches()` | `GET /branches` | Physical store info | 24 hr |

All tools return Pydantic-validated payloads. Errors surface as structured tool errors (the LLM gets a clear message it can reason about).

### 4.4 Sub-agent: Product Synthesizer

The single "real sub-agent" in the system. Justified by needing **reasoning over structured catalog data** — not just dumping JSON.

- **Trigger:** Orchestrator passes 1–10 candidate `product_ids` plus optional user constraints (size, color, max_price, intent_label)
- **Internal flow:**
  1. `asyncio.gather` parallel calls to `get_product(id)` for each candidate
  2. Second LLM call (focused system prompt: "rank these for the user's constraint, dedupe near-duplicates, highlight in-stock variants, return JSON")
  3. Returns a ranked structured brief: top 3–5 products with best matching variants, top 3 photos each, succinct one-line "why this matches" rationale
- **Why a sub-agent, not a tool:** Ranking, deduplication, and "what to emphasize" require judgment. A deterministic ranker would either be too dumb (highest stock wins) or require encoding business rules we don't yet know. The LLM is the ranker.

### 4.5 Supabase (Postgres)

Stores reference data, session memory, and operational logs. Hosts the weekly Edge Function. Reserves schema for future embeddings.

### 4.6 Reference Sync (Supabase Edge Function)

- Runs **weekly** via Supabase scheduled function (Sunday 03:00 Cairo time)
- Hits 6 reference endpoints: `/categories`, `/seasons`, `/branches`, `POST /clubs`, `POST /brands`, `GET /home`
- Diffs against current Supabase state; upserts with `updated_at` bumps only where the row actually changed
- Logs delta summary to `taxonomy_sync_runs` (added/removed/changed IDs) so we can see when Curva adds a new club, brand, or season
- Total: 6 HTTP calls per run, well under the 100/min rate limit

### 4.7 Cache Layer

In-memory LRU on the agent service (e.g., `cachetools.TTLCache` wrapped with `aiocache`-style async accessor).

- Per-tool TTLs as in §4.3
- **Single-flight pattern:** Concurrent identical requests deduped (the first request fills the cache; siblings await the same future). Prevents thundering herd on popular queries.
- Cache key includes locale (`ar`/`en`) since responses differ by language
- Hit ratio exported as a metric

## 5. Endpoint Contract

### 5.1 Request

```http
POST /agent/query
Content-Type: application/json
X-API-Key: <shared-secret>
```

```json
{
  "session_id": "20100xxxxxxxx",
  "user_message": "عندكوا قميص ريال مدريد مقاس M؟",
  "locale": "ar",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "metadata": {
    "customer_name": "أحمد",
    "customer_phone": "20100xxxxxxxx",
    "channel": "whatsapp"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `session_id` | string | yes | WhatsApp phone is the canonical key |
| `user_message` | string | yes | Latest customer turn |
| `locale` | `"ar"` \| `"en"` | no | Default `"ar"` |
| `conversation_history` | array | no | Last N turns from n8n; orchestrator merges with stored session summary |
| `metadata` | object | no | Free-form pass-through |

### 5.2 Response

```json
{
  "reply_text": "أيوة، عندنا 3 قمصان ريال مدريد مقاس M متاحة. أحسن اختيارين:",
  "products": [
    {
      "id": 10307,
      "name_ar": "...",
      "name_en": "...",
      "price": 295,
      "offer_price": null,
      "offer_ratio": null,
      "availability": "available",
      "url": "https://curvaegypt.com/product/10307",
      "images": ["https://...", "https://...", "https://..."],
      "primary_image": "https://...",
      "variants": [
        {
          "size": "M",
          "size_id": 6,
          "available": true,
          "colors": [
            {
              "name_ar": "فيروزي",
              "name_en": "Turquoise",
              "hex": "#07f8aa",
              "quantity": 65,
              "barcode": "10307-6-105"
            }
          ]
        }
      ],
      "club": {"id": 26, "name_ar": "الزمالك", "name_en": "Zamalek"},
      "brand": {"id": 8, "name_ar": "نايكي", "name_en": "Nike"},
      "season": "2026/27",
      "category": "Football Wear",
      "subcategory": "Original Quality - Curva Edition"
    }
  ],
  "follow_up_suggestions": [
    "عايز أشوف الألوان المتاحة",
    "ممكن صورة من قدام وخلف؟"
  ],
  "intent": "search",
  "diagnostics": {
    "tool_calls": 3,
    "synthesizer_invoked": true,
    "latency_ms": 8420,
    "model": "anthropic/claude-sonnet-4.6",
    "cache_hits": 1
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `reply_text` | string | Natural-language reply in the requested locale. n8n forwards this to WhatsApp as text. |
| `products` | array | 0–5 products. n8n renders each as a WhatsApp media + caption message. |
| `follow_up_suggestions` | array of strings | Optional. n8n renders as WhatsApp quick-reply buttons. |
| `intent` | enum | `"search" \| "detail" \| "availability" \| "order_intent" \| "smalltalk" \| "handoff" \| "clarification"` |
| `diagnostics` | object | For observability; n8n can ignore. |

The orchestrator's final tool call is a synthetic `finalize_response` tool. Its arguments include **both** the public response (above) and an internal `next_session_state` block:

```json
{
  "public": {  /* the response above */ },
  "next_session_state": {
    "focus_product_ids": [10307, 10306],
    "last_filters": {"club_id": 29, "category_id": 1, "season_id": 40},
    "conversation_summary": "Customer asked about Real Madrid jerseys size M; surfaced 3 candidates from 2026/27 season."
  }
}
```

The service strips `next_session_state`, writes it to the `agent_sessions` row, and returns only the `public` block to n8n. This keeps the response structured and validated by the LLM SDK's tool-use schema (rather than free-form text we have to parse).

## 6. Data Flow Examples

### Example A — Cold session

*Customer (ar):* "عندكوا قميص ريال مدريد مقاس M؟"

1. n8n → `POST /agent/query` with `session_id=phone`, message, `locale=ar`
2. Service loads `agent_sessions` row → none exists → cold start
3. Orchestrator receives: cached system prompt (taxonomy) + empty session context + user message
4. Orchestrator resolves "ريال مدريد" → `club_id=29` from cached taxonomy (no tool call needed)
5. **Tool call 1:** `search_products({club_id: 29, category_id: 1, season_id: 40, limit: 30})` → 5 products
6. **Tool call 2 (parallel within step 5 turn):** dispatch `product_synthesizer` with `product_ids=[…5 ids…]`, `constraint="size M"`
7. Synthesizer fetches 5 products in parallel, finds which have size M in stock, ranks by stock + offer_ratio, returns top 3 with photos
8. Orchestrator emits `finalize_response` with `reply_text`, `products`, suggestions
9. Service writes session row: `focus_product_ids=[id1, id2, id3]`, `last_filters={club:29, cat:1, season:40}`, `conversation_summary="Customer asked about Real Madrid jerseys size M; surfaced 3 candidates."`
10. Returns to n8n. Total: ~3 LLM calls, ~5 upstream HTTP calls.

### Example B — Follow-up turn (session continues)

*Customer:* "تمام، الأول كام بالأحمر؟"

1. Service loads session → `focus_product_ids=[id1, id2, id3]`, summary present
2. Orchestrator system prompt now includes "Recent focus: products [id1, id2, id3]. Summary: …"
3. **Tool call 1:** `get_product(id1)` → cached hit (15-min TTL) → instant return
4. Orchestrator inspects red variant, reads price + stock, formats answer with the red variant's photo URL
5. Session updated: `focus_product_ids=[id1]` (narrowed)

### Example C — Comparison query (multi-search in one turn)

*Customer:* "قارن بين قمصان أديداس ونايك لريال مدريد الموسم الحالي"

1. Orchestrator fires **two parallel `search_products` calls** in a single assistant turn (Anthropic tool-use protocol allows multiple `tool_use` blocks):
   - `search_products({club_id: 29, brand_id: 14, season_id: 40})` (Adidas)
   - `search_products({club_id: 29, brand_id: 8,  season_id: 40})` (Nike)
2. Receives both result sets in one `tool_result` round-trip
3. **Tool call:** `product_synthesizer(product_ids=[top 2 of each], constraint="comparison")`
4. Synthesizer returns 4 ranked products with comparison notes
5. Orchestrator emits side-by-side reply

### Example D — Ambiguity → clarification (no products)

*Customer:* "عايز قميص حلو"

1. Orchestrator recognizes there's no resolvable filter signal
2. Skips tool calls, emits `intent="clarification"`, `products=[]`, `reply_text="بأي فريق تحب يا فندم؟ ومناسبة عادية ولا للملعب؟"`, suggestions = top 3 popular clubs from the cached taxonomy

## 7. Database Schema

### 7.1 Reference tables

```sql
create table categories (
  id          int primary key,
  name_ar     text not null,
  name_en     text not null,
  image       text,
  updated_at  timestamptz not null default now()
);

create table subcategories (
  id          int primary key,
  category_id int not null references categories(id) on delete cascade,
  name_ar     text not null,
  name_en     text not null,
  updated_at  timestamptz not null default now()
);
create index on subcategories(category_id);

create table clubs (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  type          text,                        -- 'club' | 'nation'
  supplier      text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table brands (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table seasons (
  id          int primary key,
  name        text not null,
  updated_at  timestamptz not null default now()
);

create table branches (
  id          int primary key,
  name        text not null,
  phones      text[] not null default '{}',
  sort        int,
  updated_at  timestamptz not null default now()
);
```

### 7.2 Session memory

```sql
create table agent_sessions (
  session_id           text primary key,                 -- WhatsApp phone
  locale               text not null default 'ar',
  customer_name        text,
  focus_product_ids    int[] not null default '{}',      -- products in current conversational scope
  last_filters         jsonb,                            -- last applied search filters
  conversation_summary text,                             -- rolling summary maintained by orchestrator (~500 token cap)
  turn_count           int not null default 0,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  last_active_at       timestamptz not null default now()
);
create index on agent_sessions(last_active_at);
```

Session lifecycle:
- Read at the start of every turn (or initialized empty if missing)
- Upserted at the end of every turn — orchestrator's `finalize_response` includes `next_session_state` fields
- Sessions inactive >30 days deleted by daily cleanup function

### 7.3 Operational logs

```sql
create table agent_logs (
  id              bigserial primary key,
  session_id      text not null,
  user_message    text not null,
  reply_text      text,
  intent          text,
  tool_calls      jsonb,        -- [{name, args_redacted, latency_ms, ok, cache_hit}, ...]
  product_ids     int[],
  model           text,
  prompt_tokens   int,
  completion_tokens int,
  cached_tokens   int,
  latency_ms      int,
  ok              boolean not null,
  error           text,
  created_at      timestamptz not null default now()
);
create index on agent_logs(session_id, created_at desc);
create index on agent_logs(created_at desc);
create index on agent_logs(ok, created_at desc) where ok = false;

create table taxonomy_sync_runs (
  id            bigserial primary key,
  started_at    timestamptz not null,
  finished_at   timestamptz,
  ok            boolean,
  delta_summary jsonb,
  error         text
);
```

### 7.4 Reserved for future

```sql
-- Filled when we add text vector fallback search
create table product_embeddings (
  product_id  int primary key,
  embedding   vector(1024),
  name_concat text,
  updated_at  timestamptz
);

-- Filled when we add SigLip2 reverse image search
create table product_image_embeddings (
  image_id    int primary key,
  product_id  int not null,
  embedding   vector(768),
  image_url   text not null,
  updated_at  timestamptz
);
create index on product_image_embeddings(product_id);
```

## 8. Failure Modes

| Failure | Behavior |
|---------|----------|
| Upstream API 5xx | Retry once with 500ms backoff. If still failing: tool returns structured error; orchestrator apologizes and offers handoff (`intent="handoff"`). |
| Upstream rate-limited (429) | Tool error includes `"rate_limited"`. Orchestrator avoids that tool for this turn; cache absorbs subsequent calls. Log warning. |
| LLM provider 5xx / timeout | Single retry to OpenRouter. If still failing: return `503` to n8n with structured error so n8n can fall back to a static "I'll get a human" message. |
| Agent loop hits 12-iter cap | Force-finalize with best-effort response and `intent="handoff"`. Log as anomaly. |
| Session row corrupted / unreadable | Treat as cold start; log warning. Don't fail the turn. |
| Empty filter result | Orchestrator either asks a clarifying question OR suggests closest alternatives (different season/brand). Never silently returns empty. |
| Customer sends image (future capability) | For now: respond "هاسأل حد من الفريق يساعدك" + `intent="handoff"`. Schema reserved for SigLip2 integration. |
| Customer expresses order intent | `intent="order_intent"` in response; n8n picks this up and routes to CRM. The agent service does not place orders. |

## 9. Observability

- **Structured JSON logs** to stdout (consumed by Cloud Run / Fly logging)
- **Metrics:**
  - Tool call counts by tool name
  - Cache hit ratio
  - p50/p95/p99 turn latency
  - LLM prompt/completion/cached tokens per turn
  - Upstream `X-RateLimit-Remaining` (gauge — alert if drops below 20)
  - Error rates per failure mode
- **Sampled quality review:** 1% of turns (or all turns flagged with `ok=false` or `intent="handoff"`) flagged in `agent_logs` for human review
- **Dashboards:** Supabase Studio queries are sufficient at MVP; promote to Grafana if volume justifies

## 10. Security

- n8n is trusted; the endpoint accepts a shared `X-API-Key` header (env var, rotatable)
- No PII beyond phone number stored in our DB; customer names optional
- Supabase RLS enabled on `agent_sessions` and `agent_logs` — only the service role can read/write
- Per-session rate limit at the FastAPI layer (default: 30 turns/minute per `session_id`) to prevent runaway loops or abuse
- Outbound `User-Agent: CurvaCSAgent/1.0` so Curva can identify our traffic

## 11. Configuration (env vars)

| Var | Purpose | Default |
|-----|---------|---------|
| `OPENROUTER_API_KEY` | LLM provider auth | (required) |
| `LLM_MODEL` | Model ID for OpenRouter | `anthropic/claude-sonnet-4.6` |
| `LLM_MAX_TOOL_ITERATIONS` | Loop safety cap | `12` |
| `SUPABASE_URL` | Project URL | (required) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key | (required) |
| `CURVA_API_BASE` | Upstream base URL | `https://octane.curvaegypt.com/api` |
| `CURVA_RATE_LIMIT_WARN_AT` | Warn threshold on `X-RateLimit-Remaining` | `20` |
| `AGENT_API_KEY` | Shared secret for n8n → agent | (required) |
| `CACHE_PRODUCTS_TTL_SEC` | LRU TTL for search results | `600` |
| `CACHE_PRODUCT_TTL_SEC` | LRU TTL for product detail | `900` |
| `SESSION_TTL_DAYS` | Garbage-collect inactive sessions | `30` |

## 12. Implementation Phases

Each phase ends in something demoable end-to-end.

| Phase | Deliverable |
|-------|-------------|
| **0 — Bootstrap** | Python repo, FastAPI skeleton, Dockerfile, Supabase project provisioned, env config loader, `/healthz` |
| **1 — Reference layer** | All taxonomy migrations, Edge Function for weekly sync, manual `/admin/sync-taxonomy` trigger, `taxonomy_sync_runs` populated |
| **2 — Tools** | All 4 deterministic tools with `httpx.AsyncClient`, LRU cache, retries, rate-limit awareness, Pydantic-validated responses, unit tests against recorded fixtures |
| **3 — Orchestrator (no session, no sub-agent)** | OpenRouter client behind `LLMClient` abstraction, system prompt builder with cached taxonomy block, tool-use loop, `finalize_response` synthetic tool. End-to-end: curl `/agent/query`, get a real catalog-grounded answer. |
| **4 — Product Synthesizer sub-agent** | Parallel `get_product` fetch, ranking LLM call, integration as a dispatchable tool the orchestrator can call |
| **5 — Session memory** | Read/write `agent_sessions` per turn; orchestrator maintains rolling `conversation_summary`; multi-turn references resolve ("the first one in red") |
| **6 — Logging + observability** | `agent_logs` writes, metrics, dashboard queries, anomaly alerts |
| **7 — Hardening** | Per-session FastAPI rate limit, RLS policies, structured error responses, load test (50 concurrent sessions), docs for n8n integrators |

## 13. Open Questions (to revisit later, not blockers)

- **When does vector text search earn its keep?** Likely once we see N% of turns where the orchestrator returns empty/clarification for queries that have a clear *descriptive* signal ("green jersey with stars"). Instrument first, then decide.
- **Image input handling.** When we layer in SigLip2: the agent service grows a 6th tool `image_search(image_url)`, and the schema's `product_image_embeddings` table goes live.
- **CRM webhook.** When the orchestrator emits `intent="order_intent"`, what payload shape does the CRM want? Client-defined; n8n shapes the payload, our endpoint just signals intent.

---

**End of design.**
