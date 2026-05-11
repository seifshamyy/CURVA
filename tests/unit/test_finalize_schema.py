import pytest
from pydantic import ValidationError
from curva_agent.schemas.api import (
    AgentQueryRequest,
    AgentQueryResponse,
    ProductCard,
    FinalizeArgs,
    NextSessionState,
)


def test_agent_query_request_required_fields():
    r = AgentQueryRequest(session_id="2010", user_message="hi")
    assert r.locale == "ar"
    with pytest.raises(ValidationError):
        AgentQueryRequest(user_message="hi")


def test_agent_query_response_minimal():
    r = AgentQueryResponse(reply_text="hi", products=[], intent="smalltalk")
    assert r.diagnostics is None


def test_product_card_url_and_images():
    card = ProductCard(
        id=10307,
        name_ar="..", name_en="..",
        price=295, offer_price=None, offer_ratio=None,
        availability="available",
        url="https://curvaegypt.com/product/10307",
        images=["https://x/y.webp"],
        primary_image="https://x/y.webp",
        variants=[], club=None, brand=None,
        season=None, category=None, subcategory=None,
    )
    assert card.id == 10307


def test_finalize_args_round_trip():
    args = FinalizeArgs(
        public=AgentQueryResponse(reply_text="hi", products=[], intent="search"),
        next_session_state=NextSessionState(
            focus_product_ids=[1, 2], last_filters={"club_id": 26},
            conversation_summary="asked about Zamalek",
        ),
    )
    j = args.model_dump_json()
    parsed = FinalizeArgs.model_validate_json(j)
    assert parsed.public.intent == "search"
    assert parsed.next_session_state.focus_product_ids == [1, 2]