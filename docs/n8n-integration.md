# n8n Integration Guide

The Curva CS Agent exposes ONE endpoint that n8n calls for every incoming
WhatsApp message.

## Request

```http
POST {AGENT_URL}/agent/query
X-API-Key: {AGENT_API_KEY}
Content-Type: application/json

{
  "session_id": "{{ $json.from }}",
  "user_message": "{{ $json.text }}",
  "locale": "ar",
  "conversation_history": [],
  "metadata": {
    "customer_name": "{{ $json.profile.name }}",
    "customer_phone": "{{ $json.from }}",
    "channel": "whatsapp"
  }
}
```

## Response

```json
{
  "reply_text": "string — render as WhatsApp text message",
  "products": [{ "id": ..., "primary_image": "url", "images": [...], ... }],
  "follow_up_suggestions": ["string", "string"],
  "intent": "search | detail | availability | order_intent | smalltalk | handoff | clarification",
  "diagnostics": { ... }
}
```

## Rendering products

For each product in `products`:
1. Send `primary_image` as a WhatsApp media message with a short caption
   (name + price).
2. Optionally send 2–3 more images from `images` for the same product.

For each `follow_up_suggestion`, render as a WhatsApp quick-reply button.

## Intent routing

- `order_intent` — route the conversation context to the CRM workflow.
- `handoff` — escalate to a human CS rep (notify ops channel).
- All other intents — just reply.

## Error handling

- `401` — bad/missing API key. Check `X-API-Key` header.
- `429` — session rate-limited (>30 turns/minute). Throttle in n8n.
- `5xx` — service issue. Fall back to a static "I'll get a human" message.