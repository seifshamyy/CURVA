"""Public endpoint contract + orchestrator's `finalize_response` tool args."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from curva_agent.schemas.tools import VariantBySize


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------- Request ----------
class HistoryTurn(_Base):
    role: Literal["user", "assistant"]
    content: str


class RequestMetadata(_Base):
    customer_name: str | None = None
    customer_phone: str | None = None
    channel: str | None = None


class AgentQueryRequest(_Base):
    session_id: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    locale: Literal["ar", "en"] = "ar"
    conversation_history: list[HistoryTurn] = Field(default_factory=list)
    metadata: RequestMetadata | None = None


# ---------- Response ----------
class ProductCard(_Base):
    id: int
    name_ar: str
    name_en: str
    price: int
    offer_price: int | None
    offer_ratio: str | None
    availability: str
    url: str
    images: list[str]
    primary_image: str
    variants: list[VariantBySize]
    club: dict[str, Any] | None
    brand: dict[str, Any] | None
    season: str | None
    category: str | None
    subcategory: str | None


Intent = Literal[
    "search", "detail", "availability", "order_intent",
    "smalltalk", "handoff", "clarification",
]


class Diagnostics(_Base):
    tool_calls: int
    synthesizer_invoked: bool = False
    latency_ms: int = 0
    model: str = ""
    cache_hits: int = 0
    iterations: int = 0
    tool_calls_detail: list[dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


class AgentQueryResponse(_Base):
    reply_text: str
    products: list[ProductCard] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    intent: Intent
    diagnostics: Diagnostics | None = None


# ---------- finalize_response tool args ----------
class NextSessionState(_Base):
    focus_product_ids: list[int] = Field(default_factory=list)
    last_filters: dict[str, Any] | None = None
    conversation_summary: str = ""


class FinalizeArgs(_Base):
    public: AgentQueryResponse
    next_session_state: NextSessionState