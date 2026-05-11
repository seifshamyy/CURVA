"""The Product Synthesizer sub-agent."""
import json
from typing import Any
from curva_agent.llm.client import LLMClient, LLMMessage
from curva_agent.observability.logging import get_logger
from curva_agent.schemas.tools import (
    ProductSynthesizerInput,
    ProductSynthesizerOutput,
    SynthesizedCandidate,
    GetProductOutput,
)
from curva_agent.tools._parallel import fetch_products_parallel
from curva_agent.tools.base import Tool

log = get_logger("synthesizer")

_SYS_PROMPT = """\
You are a ranking sub-agent for the Curva CS bot. You are NOT talking to the
customer — only the master agent reads your output.

Input: a list of candidate products (full details) and a customer constraint.
Output: a JSON object {"candidates":[{"id":N,"rationale":"..."}, ...]} ranking
the candidates by how well they match the constraint. Drop near-duplicates.
Cap output at 5 candidates. If no constraint, rank by stock availability and
recency (favor available, higher-stock variants).

Rationale: ONE short line in the requested locale, ≤80 chars, explaining the
match (e.g. "Size M available, on sale", "Closest color match").

Return ONLY the JSON object. No prose.
"""


class ProductSynthesizerTool(Tool[ProductSynthesizerInput, ProductSynthesizerOutput]):
    name = "product_synthesizer"
    description = (
        "Given 1-10 candidate product IDs and an optional user constraint, "
        "fetch full details for each in parallel and return a ranked, deduped "
        "list of the best matches with photos, variants, and one-line "
        "rationales. Use after search_products to drill into candidates."
    )
    input_model = ProductSynthesizerInput

    def __init__(self, *, get_product: Any, llm: LLMClient) -> None:
        self._get_product = get_product
        self._llm = llm

    async def run(
        self, args: ProductSynthesizerInput, *, locale: str = "ar"
    ) -> ProductSynthesizerOutput:
        details: list[GetProductOutput] = await fetch_products_parallel(
            self._get_product, args.product_ids, locale=locale
        )
        if not details:
            return ProductSynthesizerOutput(candidates=[])

        compact = [
            {
                "id": d.id,
                "name": d.name,
                "price": d.init_price,
                "offer_price": d.offer_price,
                "availability": d.availability,
                "variants": [
                    {
                        "size": v.size,
                        "available": v.available,
                        "colors": [
                            {"name": c.name, "qty": c.quantity} for c in v.colors
                        ],
                    }
                    for v in d.variants
                ],
            }
            for d in details
        ]
        user_msg = json.dumps(
            {"constraint": args.constraint, "locale": locale, "candidates": compact},
            ensure_ascii=False,
        )

        resp = await self._llm.complete(
            system_blocks=[{"type": "text", "text": _SYS_PROMPT}],
            messages=[LLMMessage(role="user", content=user_msg)],
            tools=[],
            temperature=0.1,
            max_tokens=1024,
        )

        rankings = _parse_rankings(resp.text)
        by_id = {d.id: d for d in details}
        candidates: list[SynthesizedCandidate] = []
        seen: set[int] = set()
        order = [r["id"] for r in rankings if r["id"] in by_id]
        for pid in order + [d.id for d in details if d.id not in order]:
            if pid in seen:
                continue
            seen.add(pid)
            d = by_id[pid]
            rationale = next((r["rationale"] for r in rankings if r["id"] == pid), "")
            candidates.append(
                SynthesizedCandidate(
                    id=d.id,
                    name=d.name,
                    price=d.init_price,
                    offer_price=d.offer_price,
                    primary_image=d.primary_image,
                    images=d.images[:3],
                    best_variants=[v for v in d.variants if v.available][:3] or d.variants[:3],
                    url=d.url,
                    rationale=rationale,
                )
            )
            if len(candidates) >= 5:
                break
        return ProductSynthesizerOutput(candidates=candidates)


def _parse_rankings(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            log.warning("synthesizer_invalid_json", text=text[:200])
            return []
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            log.warning("synthesizer_invalid_json", text=text[:200])
            return []
    cands = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(cands, list):
        return []
    out: list[dict[str, Any]] = []
    for c in cands:
        if isinstance(c, dict) and isinstance(c.get("id"), int):
            out.append({"id": c["id"], "rationale": str(c.get("rationale") or "")})
    return out