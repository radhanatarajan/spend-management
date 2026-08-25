import json

import ollama
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from src.core.config import settings
from src.schemas.spend import SpendAccountGapRow, SpendDepartmentGapRow, SpendActivityGapRow


class GapAgentUnavailableError(Exception):
    """Raised when the local Ollama server can't be reached."""


# ── Tool implementations ─────────────────────────────────────────────────────
# Each function runs a fixed, parameterized query against one of the existing
# gap views (server/src/db/init_db.py:333-409). Only `limit` is model-controlled,
# and it's bound as a SQL parameter, never string-interpolated.

def get_account_gaps(db: Session, limit: int = 50) -> dict:
    total = db.execute(sa_text("SELECT COUNT(*) FROM v_spend_account_gaps")).scalar()
    rows = db.execute(
        sa_text(
            "SELECT account_number, account_group, account_sub_group, cost_element, "
            "spend_row_count, earliest_month, latest_month "
            "FROM v_spend_account_gaps LIMIT :lim"
        ),
        {"lim": limit},
    ).mappings().all()
    return {
        "total_gap_count": total,
        "returned_count": len(rows),
        "rows": [SpendAccountGapRow(**dict(r)).model_dump(mode="json") for r in rows],
    }


def get_department_gaps(db: Session, limit: int = 50) -> dict:
    total = db.execute(sa_text("SELECT COUNT(*) FROM v_spend_department_gaps")).scalar()
    rows = db.execute(
        sa_text(
            "SELECT department_code, department_name, "
            "spend_row_count, earliest_month, latest_month "
            "FROM v_spend_department_gaps LIMIT :lim"
        ),
        {"lim": limit},
    ).mappings().all()
    return {
        "total_gap_count": total,
        "returned_count": len(rows),
        "rows": [SpendDepartmentGapRow(**dict(r)).model_dump(mode="json") for r in rows],
    }


def get_activity_gaps(db: Session, limit: int = 50) -> dict:
    total = db.execute(sa_text("SELECT COUNT(*) FROM v_spend_activity_gaps")).scalar()
    rows = db.execute(
        sa_text(
            "SELECT activity_id, department_code, department_name, account_group, "
            "spend_row_count, earliest_month, latest_month "
            "FROM v_spend_activity_gaps LIMIT :lim"
        ),
        {"lim": limit},
    ).mappings().all()
    return {
        "total_gap_count": total,
        "returned_count": len(rows),
        "rows": [SpendActivityGapRow(**dict(r)).model_dump(mode="json") for r in rows],
    }


TOOL_IMPL = {
    "get_account_gaps": get_account_gaps,
    "get_department_gaps": get_department_gaps,
    "get_activity_gaps": get_activity_gaps,
}

_LIMIT_PARAM = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "description": "Max number of gap rows to return. Default 50.",
        }
    },
    "required": [],
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_account_gaps",
            "description": (
                "Return spend transactions whose Oracle account number has no matching "
                "entry in the account_numbers reference table (an account-level data "
                "quality gap). Each row is a distinct account_number with a count of "
                "affected spend rows and the earliest/latest month seen."
            ),
            "parameters": _LIMIT_PARAM,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_department_gaps",
            "description": (
                "Return spend transactions whose Oracle department code has no matching "
                "entry in the departments reference table (a department-level data "
                "quality gap). Each row is a distinct department_code with a count of "
                "affected spend rows and the earliest/latest month seen."
            ),
            "parameters": _LIMIT_PARAM,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activity_gaps",
            "description": (
                "Return spend transactions whose activity ID has no matching entry in "
                "the activity_ids reference table (an activity-level data quality gap). "
                "Note: activity ID gaps are usually self-healing on the next server "
                "startup, so a near-zero count here is expected. Each row is a distinct "
                "activity_id with a count of affected spend rows and the earliest/latest "
                "month seen."
            ),
            "parameters": _LIMIT_PARAM,
        },
    },
]


# ── Agent loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a data-quality assistant for a spend management system. You can call "
    "tools to look up spend records that reference an account number, department "
    "code, or activity ID that doesn't exist in the reference tables (a 'gap'). "
    "Always call a tool before answering questions about gaps — do not guess. "
    "Summarize findings concisely, citing counts and specific codes/departments "
    "where relevant. You only have access to these three gap-lookup tools — if "
    "asked about anything else (e.g. total spend, budgets, contracts), say that's "
    "outside what you can look up."
)

MAX_ITERATIONS = 5


async def run_agent_chat(db: Session, messages: list[dict]) -> dict:
    client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
    convo = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    tools_called = []

    for _ in range(MAX_ITERATIONS):
        try:
            response = await client.chat(model=settings.OLLAMA_MODEL, messages=convo, tools=TOOLS)
        except (ConnectionError, OSError) as exc:
            raise GapAgentUnavailableError(
                "Local Ollama server is unreachable. Make sure `ollama serve` is running "
                f"and the model '{settings.OLLAMA_MODEL}' is pulled."
            ) from exc

        msg = response.message
        convo.append({"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls})

        if not msg.tool_calls:
            return {"message": msg.content, "tools_called": tools_called}

        for call in msg.tool_calls:
            fn = TOOL_IMPL.get(call.function.name)
            arguments = dict(call.function.arguments or {})
            if fn is None:
                result = {"error": f"unknown tool '{call.function.name}'"}
            else:
                result = fn(db, **arguments)
            tools_called.append({"name": call.function.name, "arguments": arguments})
            convo.append({
                "role": "tool",
                "content": json.dumps(result, default=str),
                "name": call.function.name,
            })

    return {
        "message": (
            "I wasn't able to finish reasoning about this within the allowed number "
            "of steps. Try asking a more specific question."
        ),
        "tools_called": tools_called,
    }
