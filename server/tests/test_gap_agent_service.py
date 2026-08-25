from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text as sa_text

from tests.conftest import make_spend
from tests.test_reference import make_department, make_account, make_activity
from src.services.gap_agent_service import get_account_gaps, get_department_gaps, get_activity_gaps


def seed(db, rows):
    db.add_all(rows)
    db.commit()


@pytest.fixture(autouse=True)
def _gap_views(db):
    """SQLite doesn't support MySQL's CREATE OR REPLACE VIEW; create the three
    gap views idempotently (CREATE VIEW IF NOT EXISTS), using the exact SELECT
    bodies from server/src/db/init_db.py:333-409. These views use only portable
    ANSI SQL (LEFT JOIN / WHERE ... IS NULL / GROUP BY / aggregates), so they
    run unmodified against SQLite.

    This runs via the `db` fixture (not a module-level `engine` import) on
    purpose: pytest loads conftest.py as its own `conftest` module for fixture
    resolution, which is a *separate* sys.modules entry (and therefore a
    separate in-memory SQLite `engine`) from what an explicit
    `from tests.conftest import engine` would give you. Creating the views
    through the `db` fixture guarantees they land in the exact database the
    `client`/`admin_client` fixtures actually query against.

    The `reset_db` autouse fixture in conftest.py only does
    Base.metadata.create_all()/drop_all() per test, which never touches raw
    SQL views (they aren't ORM-mapped) — so re-creating them here on every
    test is required, not just a one-time bootstrap. It's cheap and a no-op
    once already present, since `IF NOT EXISTS` guards it.
    """
    db.execute(sa_text("""
            CREATE VIEW IF NOT EXISTS v_spend_account_gaps AS
            SELECT
                s.oracle_account_number                          AS account_number,
                s.oracle_account_group                           AS account_group,
                s.oracle_account_sub_group                       AS account_sub_group,
                s.oracle_cost_element                            AS cost_element,
                COUNT(*)                                         AS spend_row_count,
                MIN(s.month_label)                               AS earliest_month,
                MAX(s.month_label)                               AS latest_month
            FROM spend s
            LEFT JOIN account_numbers an
                   ON s.oracle_account_number = an.account_number
            WHERE s.oracle_account_number IS NOT NULL
              AND an.id IS NULL
            GROUP BY
                s.oracle_account_number,
                s.oracle_account_group,
                s.oracle_account_sub_group,
                s.oracle_cost_element
        """))
    db.execute(sa_text("""
            CREATE VIEW IF NOT EXISTS v_spend_department_gaps AS
            SELECT
                s.oracle_department                              AS department_code,
                s.oracle_department_name                         AS department_name,
                COUNT(*)                                         AS spend_row_count,
                MIN(s.month_label)                               AS earliest_month,
                MAX(s.month_label)                               AS latest_month
            FROM spend s
            LEFT JOIN departments d
                   ON s.oracle_department = d.department_code
            WHERE s.oracle_department IS NOT NULL
              AND d.department_code IS NULL
            GROUP BY
                s.oracle_department,
                s.oracle_department_name
        """))
    db.execute(sa_text("""
            CREATE VIEW IF NOT EXISTS v_spend_activity_gaps AS
            SELECT
                s.activity_id,
                s.oracle_department                              AS department_code,
                s.oracle_department_name                         AS department_name,
                s.oracle_account_group                           AS account_group,
                COUNT(*)                                         AS spend_row_count,
                MIN(s.month_label)                               AS earliest_month,
                MAX(s.month_label)                               AS latest_month
            FROM spend s
            LEFT JOIN activity_ids ai
                   ON s.activity_id = ai.activity_id
            WHERE s.activity_id IS NOT NULL
              AND ai.activity_id IS NULL
            GROUP BY
                s.activity_id,
                s.oracle_department,
                s.oracle_department_name,
                s.oracle_account_group
        """))
    db.commit()


# ── Tool function tests ──────────────────────────────────────────────────────

class TestGetAccountGaps:
    def test_empty_when_no_gaps(self, db):
        acct = make_account(db, account_group="R&D", cost_element="Salaries")
        seed(db, [make_spend(oracle_account_number=acct.account_number)])
        result = get_account_gaps(db)
        assert result["total_gap_count"] == 0
        assert result["rows"] == []

    def test_flags_unmatched_account(self, db):
        seed(db, [make_spend(
            oracle_account_number="ACC-UNKNOWN",
            oracle_account_group="R&D",
            oracle_account_sub_group="Cloud",
            oracle_cost_element="Hosting",
            month_label="Jan 2026",
        )])
        result = get_account_gaps(db)
        assert result["total_gap_count"] == 1
        row = result["rows"][0]
        assert row["account_number"] == "ACC-UNKNOWN"
        assert row["spend_row_count"] == 1
        assert row["earliest_month"] == "Jan 2026"
        assert row["latest_month"] == "Jan 2026"

    def test_aggregates_multiple_rows_for_same_gap(self, db):
        seed(db, [
            make_spend(oracle_account_number="ACC-UNKNOWN", month_label="Jan 2026"),
            make_spend(oracle_account_number="ACC-UNKNOWN", month_label="Mar 2026"),
        ])
        result = get_account_gaps(db)
        assert result["total_gap_count"] == 1
        assert result["rows"][0]["spend_row_count"] == 2

    def test_limit_caps_returned_rows_but_not_total(self, db):
        seed(db, [make_spend(oracle_account_number=f"ACC-GAP-{i}") for i in range(5)])
        result = get_account_gaps(db, limit=2)
        assert result["total_gap_count"] == 5
        assert result["returned_count"] == 2
        assert len(result["rows"]) == 2


class TestGetDepartmentGaps:
    def test_flags_unmatched_department(self, db):
        seed(db, [make_spend(oracle_department="9999", oracle_department_name="Ghost Dept")])
        result = get_department_gaps(db)
        assert result["total_gap_count"] == 1
        assert result["rows"][0]["department_code"] == "9999"

    def test_matched_department_excluded(self, db):
        dept = make_department(db, code="1100", name="Engineering")
        seed(db, [make_spend(oracle_department=dept.department_code, oracle_department_name=dept.department_name)])
        result = get_department_gaps(db)
        assert result["total_gap_count"] == 0


class TestGetActivityGaps:
    def test_flags_unmatched_activity(self, db):
        seed(db, [make_spend(activity_id="ACT-MISSING")])
        result = get_activity_gaps(db)
        assert result["total_gap_count"] == 1
        assert result["rows"][0]["activity_id"] == "ACT-MISSING"

    def test_matched_activity_excluded(self, db):
        make_activity(db, activity_id="ACT-100", department_code="1100")
        seed(db, [make_spend(activity_id="ACT-100")])
        result = get_activity_gaps(db)
        assert result["total_gap_count"] == 0

    def test_null_activity_id_excluded(self, db):
        seed(db, [make_spend(activity_id=None)])
        result = get_activity_gaps(db)
        assert result["total_gap_count"] == 0


# ── Chat endpoint tests (Ollama mocked — no real model call in CI) ──────────

class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeResponse:
    def __init__(self, content=None, tool_calls=None):
        self.message = _FakeMessage(content=content, tool_calls=tool_calls)


class TestGapAgentChatEndpoint:
    def test_requires_auth(self, client):
        resp = client.post("/api/spend/reports/gaps-agent/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 401

    def test_happy_path_calls_tool_and_returns_final_message(self, db, admin_client):
        seed(db, [make_spend(oracle_account_number="ACC-UNKNOWN")])

        tool_call_response = _FakeResponse(
            content=None,
            tool_calls=[_FakeToolCall("get_account_gaps", {})],
        )
        final_response = _FakeResponse(content="There is 1 account gap: ACC-UNKNOWN.", tool_calls=None)

        with patch(
            "src.services.gap_agent_service.ollama.AsyncClient.chat",
            new_callable=AsyncMock,
            side_effect=[tool_call_response, final_response],
        ) as mock_chat:
            resp = admin_client.post(
                "/api/spend/reports/gaps-agent/chat",
                json={"messages": [{"role": "user", "content": "what account gaps exist?"}]},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "There is 1 account gap: ACC-UNKNOWN."
        assert body["tools_called"] == [{"name": "get_account_gaps", "arguments": {}}]

        # confirm the second call's message history actually carries the real tool result
        second_call_messages = mock_chat.call_args_list[1].kwargs["messages"]
        tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
        assert len(tool_messages) == 1
        assert "ACC-UNKNOWN" in tool_messages[0]["content"]

    def test_ollama_unreachable_returns_503(self, admin_client):
        with patch(
            "src.services.gap_agent_service.ollama.AsyncClient.chat",
            new_callable=AsyncMock,
            side_effect=ConnectionError("connection refused"),
        ):
            resp = admin_client.post(
                "/api/spend/reports/gaps-agent/chat",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
        assert resp.status_code == 503

    def test_max_iterations_guard_stops_infinite_tool_loop(self, admin_client):
        always_tool_call = _FakeResponse(content=None, tool_calls=[_FakeToolCall("get_account_gaps", {})])
        with patch(
            "src.services.gap_agent_service.ollama.AsyncClient.chat",
            new_callable=AsyncMock,
            return_value=always_tool_call,
        ) as mock_chat:
            resp = admin_client.post(
                "/api/spend/reports/gaps-agent/chat",
                json={"messages": [{"role": "user", "content": "loop forever"}]},
            )
        assert resp.status_code == 200
        assert mock_chat.call_count == 5
        assert "allowed number of steps" in resp.json()["message"]
