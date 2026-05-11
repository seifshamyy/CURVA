"""The synthetic `finalize_response` tool — the orchestrator's exit gate."""
from curva_agent.schemas.api import FinalizeArgs

FINALIZE_TOOL_NAME = "finalize_response"

FINALIZE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": FINALIZE_TOOL_NAME,
        "description": (
            "REQUIRED final tool call. Provide the customer-facing reply (reply_text, products, "
            "follow_up_suggestions, intent) and session state (focus_product_ids, "
            "conversation_summary) as top-level fields. After calling this you MUST stop — do "
            "not call any further tools."
        ),
        "parameters": FinalizeArgs.model_json_schema(),
    },
}