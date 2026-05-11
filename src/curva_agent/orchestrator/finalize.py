"""The synthetic `finalize_response` tool — the orchestrator's exit gate."""
from curva_agent.schemas.api import FinalizeArgs

FINALIZE_TOOL_NAME = "finalize_response"

FINALIZE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": FINALIZE_TOOL_NAME,
        "description": (
            "REQUIRED final tool call. Emits the structured response to the customer "
            "and the updated session state. After calling this you MUST stop — do "
            "not call any further tools."
        ),
        "parameters": FinalizeArgs.model_json_schema(),
    },
}