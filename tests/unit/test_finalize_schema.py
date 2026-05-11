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
        reply_text="hi",
        products=[],
        follow_up_suggestions=[],
        intent="search",
        focus_product_ids=[1, 2],
        last_filters={"club_id": 26},
        conversation_summary="asked about Zamalek",
    )
    j = args.model_dump_json()
    parsed = FinalizeArgs.model_validate_json(j)
    assert parsed.intent == "search"
    assert parsed.focus_product_ids == [1, 2]
    assert parsed.to_response().reply_text == "hi"
    assert parsed.to_session_state().conversation_summary == "asked about Zamalek"


def test_finalize_args_empty_defaults():
    args = FinalizeArgs.model_validate({})
    assert args.reply_text == ""
    assert args.products == []
    assert args.intent == "search"
    assert args.focus_product_ids == []
    assert args.conversation_summary == ""