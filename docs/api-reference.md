# Curva CS Agent — API Documentation

Base URL: `https://curva-production.up.railway.app`

All endpoints require the `X-API-Key` header unless noted otherwise.

---

## Authentication

| Header | Value |
|--------|-------|
| `X-API-Key` | Your shared secret (configured via `AGENT_API_KEY` env var) |
| `Content-Type` | `application/json` (for POST endpoints) |

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/healthz` | No | Liveness probe |
| `GET` | `/` | No | Service metadata |
| `POST` | `/agent/query` | Yes | Primary agent endpoint |
| `POST` | `/admin/sync-taxonomy` | Yes | Manual taxonomy refresh |

---

## `GET /healthz`

Liveness check. No auth required.

### cURL

```bash
curl -s https://curva-production.up.railway.app/healthz
```

### Response

```json
{"status": "ok"}
```

---

## `GET /`

Service metadata. No auth required.

### cURL

```bash
curl -s https://curva-production.up.railway.app/
```

### Response

```json
{"service": "curva-cs-agent", "version": "0.1.0"}
```

---

## `POST /agent/query`

The primary endpoint. n8n calls this for every incoming WhatsApp message. The agent runs a full tool-use loop (search catalog, check stock, fetch offers, list branches) and returns a structured response with products, suggestions, and intent.

### cURL — Arabic (Zamalek jersey search)

```bash
curl -s -X POST https://curva-production.up.railway.app/agent/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20100123456",
    "user_message": "عندكوا قميص زمالك؟",
    "locale": "ar"
  }'
```

### cURL — English (product detail with size check)

```bash
curl -s -X POST https://curva-production.up.railway.app/agent/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20100765432",
    "user_message": "Do you have Real Madrid jerseys size M?",
    "locale": "en"
  }'
```

### cURL — Follow-up turn (session continues)

```bash
curl -s -X POST https://curva-production.up.railway.app/agent/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20100123456",
    "user_message": "الأحمر متاح؟",
    "locale": "ar",
    "metadata": {
      "customer_name": "أحمد",
      "customer_phone": "20100123456",
      "channel": "whatsapp"
    }
  }'
```

### cURL — Current offers

```bash
curl -s -X POST https://curva-production.up.railway.app/agent/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20100999888",
    "user_message": "ايه العروض عندكم؟",
    "locale": "ar"
  }'
```

### cURL — Branch locations

```bash
curl -s -X POST https://curva-production.up.railway.app/agent/query \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "20100111222",
    "user_message": "فين فروعكم؟",
    "locale": "ar"
  }'
```

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `string` | **Yes** | WhatsApp phone number (e.g. `"20100123456"`). Used as the session key for conversation memory. |
| `user_message` | `string` | **Yes** | The customer's message (Arabic or English). |
| `locale` | `"ar"` \| `"en"` | No | Response language. Default `"ar"`. |
| `conversation_history` | `array` | No | Last N turns from n8n. Each entry: `{"role": "user"\|"assistant", "content": "..."}` |
| `metadata` | `object` | No | Optional pass-through metadata. |

**Full request schema:**

```json
{
  "session_id": "20100123456",
  "user_message": "عندكوا قميص زمالك؟",
  "locale": "ar",
  "conversation_history": [
    {"role": "user", "content": "مرحبا"},
    {"role": "assistant", "content": "أهلاً! ازاي أقدر أساعدك؟"}
  ],
  "metadata": {
    "customer_name": "أحمد",
    "customer_phone": "20100123456",
    "channel": "whatsapp"
  }
}
```

### Response Body

| Field | Type | Description |
|-------|------|-------------|
| `reply_text` | `string` | Natural-language reply in the requested locale. Send this to WhatsApp as a text message. |
| `products` | `array[ProductCard]` | 0–5 product cards. Send each as a WhatsApp media message with caption. |
| `follow_up_suggestions` | `array[string]` | Quick-reply suggestions for WhatsApp buttons. |
| `intent` | `string` | One of: `search`, `detail`, `availability`, `order_intent`, `smalltalk`, `handoff`, `clarification` |
| `diagnostics` | `object` \| `null` | Observability data. Can be ignored by n8n. |

**ProductCard object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Product ID |
| `name_ar` | `string` | Arabic name |
| `name_en` | `string` | English name |
| `price` | `int` | Original price in EGP |
| `offer_price` | `int` \| `null` | Discounted price in EGP (null if no offer) |
| `offer_ratio` | `string` \| `null` | Discount percentage string (e.g. `"35"`) |
| `availability` | `string` | `"available"` or `"unavailable"` |
| `url` | `string` | Product page URL on curvaegypt.com |
| `images` | `array[string]` | Up to 3 image URLs |
| `primary_image` | `string` | Main product image URL |
| `variants` | `array[VariantBySize]` | Size/color stock breakdown |
| `club` | `object` \| `null` | `{"name_en": "Zamalek", "name_ar": "الزمالك"}` |
| `brand` | `object` \| `null` | `{"name_en": "Nike", "name_ar": "نايكي"}` |
| `season` | `string` \| `null` | e.g. `"2025/26"` |
| `category` | `string` \| `null` | e.g. `"Football Wear"` |
| `subcategory` | `string` \| `null` | e.g. `"Original Quality - Curva Edition"` |

**VariantBySize object:**

| Field | Type | Description |
|-------|------|-------------|
| `size` | `string` | Size label (e.g. `"M"`, `"L"`, `"XL"`) |
| `size_id` | `int` | Size ID |
| `price` | `int` | Price for this variant |
| `offer_price` | `int` \| `null` | Discounted price |
| `available` | `bool` | Whether this size has stock |
| `colors` | `array[ColorOption]` | Available colors with stock quantities |

**ColorOption object:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Color name (e.g. `"Turquoise"`) |
| `hex` | `string` \| `null` | Hex color code (e.g. `"#07f8aa"`) |
| `quantity` | `int` | Stock count |
| `barcode` | `string` | Product barcode |

**Diagnostics object:**

| Field | Type | Description |
|-------|------|-------------|
| `tool_calls` | `int` | Number of tool calls in this turn |
| `synthesizer_invoked` | `bool` | Whether the product synthesizer sub-agent ran |
| `latency_ms` | `int` | Total turn latency in milliseconds |
| `model` | `string` | LLM model used (e.g. `"anthropic/claude-sonnet-4.6"`) |
| `cache_hits` | `int` | Number of cache hits on upstream API calls |
| `iterations` | `int` | Number of agent loop iterations |
| `tool_calls_detail` | `array` | Per-tool call details (name, args, ok, latency_ms) |
| `prompt_tokens` | `int` | Total prompt tokens |
| `completion_tokens` | `int` | Total completion tokens |
| `cached_tokens` | `int` | Prompt cache hit tokens |

### Full response example

```json
{
  "reply_text": "أيوه! عندنا قمصان زمالك كتير جداً 🤍 الأسعار من 125 لـ 325 جنيه.",
  "products": [
    {
      "id": 10276,
      "name_ar": "قميص الزمالك الأساسي 2025/26 بشعارات ثري دي AT-161",
      "name_en": "Zamalek Home Jersey 2025/26 3D Badges AT-161",
      "price": 300,
      "offer_price": null,
      "offer_ratio": null,
      "availability": "available",
      "url": "https://curvaegypt.com/product/10276",
      "images": [
        "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/products/1777993449-WhatsApp-Image-2026-05-05-at-16-50-03.webp?v=1"
      ],
      "primary_image": "https://curva-app.nyc3.cdn.digitaloceanspaces.com/assets/uploads/products/1777993449-WhatsApp-Image-2026-05-05-at-16-50-03.webp?v=1",
      "variants": [],
      "club": {"name_en": "Zamalek", "name_ar": "الزمالك"},
      "brand": null,
      "season": "2025/26",
      "category": "Football Wear",
      "subcategory": null
    }
  ],
  "follow_up_suggestions": [
    "عايز مقاس معين؟",
    "عايز نسخة لاعبين أو هاي كوبي؟",
    "عندكوا قمصان زمالك كلاسيك؟"
  ],
  "intent": "search",
  "diagnostics": {
    "tool_calls": 1,
    "synthesizer_invoked": false,
    "latency_ms": 34319,
    "model": "anthropic/claude-sonnet-4.6",
    "cache_hits": 0,
    "iterations": 2,
    "tool_calls_detail": [
      {"name": "search_products", "args": {"club_id": 26, "limit": 10}, "ok": true, "latency_ms": 272}
    ],
    "prompt_tokens": 39676,
    "completion_tokens": 2679,
    "cached_tokens": 18660
  }
}
```

### Intent routing guide (for n8n)

| Intent | Action |
|--------|--------|
| `search` | Reply normally — products found |
| `detail` | Reply normally — product detail shown |
| `availability` | Reply normally — stock info provided |
| `order_intent` | **Route to CRM** — customer wants to buy |
| `smalltalk` | Reply normally — casual conversation |
| `clarification` | Reply normally — agent asked a follow-up |
| `handoff` | **Escalate to human** — agent couldn't help |

### Error responses

**401 Unauthorized** — missing or wrong API key:
```json
{"detail": "invalid or missing api key"}
```

**429 Too Many Requests** — session rate-limited (>30 turns/minute):
```json
{"detail": "too many turns; slow down"}
```

**500 Internal Server Error** — LLM provider timeout or unexpected error. Fall back to a static message in n8n:
```json
{"detail": "Internal Server Error"}
```

---

## `POST /admin/sync-taxonomy`

Refresh reference data (categories, clubs, brands, seasons, branches) from the Curva API into Supabase. Called manually or weekly via the Edge Function cron.

### cURL

```bash
curl -s -X POST https://curva-production.up.railway.app/admin/sync-taxonomy \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

### Response

```json
{
  "ok": true,
  "counts": {
    "categories": 7,
    "subcategories": 72,
    "clubs": 117,
    "brands": 76,
    "seasons": 41,
    "branches": 16
  },
  "error": null,
  "started_at": "2026-05-11T10:17:33.377189+00:00"
}
```

If a partial failure occurs (e.g. one upstream endpoint is down), `ok` will be `false` and `error` will contain details:

```json
{
  "ok": false,
  "counts": {
    "categories": 7,
    "subcategories": 72,
    "seasons": 41,
    "branches": 16
  },
  "error": "clubs: 500 on /clubs; brands: 500 on /brands",
  "started_at": "2026-05-11T10:00:07.451129+00:00"
}
```

---

## Rate limiting

Each `session_id` (phone number) is limited to **30 requests per minute**. Exceeding this returns `429`.

---

## Session memory

The agent maintains per-session state keyed by `session_id` (phone number):
- **Focus products** — which products the customer is currently interested in
- **Last search filters** — club, brand, season, category from the last search
- **Conversation summary** — rolling ~500-token summary maintained by the LLM

Sessions expire after 30 days of inactivity.

---

## Deployment

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for Claude Sonnet 4.6 |
| `LLM_MODEL` | Model ID (default: `anthropic/claude-sonnet-4.6`) |
| `LLM_MAX_TOOL_ITERATIONS` | Max tool loop iterations (default: `12`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `CURVA_API_BASE` | Curva upstream API base (default: `https://octane.curvaegypt.com/api`) |
| `AGENT_API_KEY` | Shared secret for n8n → agent auth |
| `SESSION_RATE_LIMIT_PER_MIN` | Per-session rate limit (default: `30`) |
| `LOG_LEVEL` | Structured log level (default: `INFO`) |