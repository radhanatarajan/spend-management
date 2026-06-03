import random
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import select, func, text

from src.db.base import Base
from src.db.session import engine, SessionLocal
from src.models import spend as _spend_module     # noqa: F401 — registers Spend with Base.metadata
from src.models import user as _user_module       # noqa: F401 — registers User with Base.metadata
from src.models import contract as _contract_module  # noqa: F401 — registers Contract/ContractLine with Base.metadata
from src.models import budget as _budget_module   # noqa: F401 — registers BudgetScenario/BudgetEntry/BudgetNcConfig with Base.metadata
from src.models import reference as _reference_module  # noqa: F401 — registers Department/AccountNumber/ProjectId/ActivityId with Base.metadata


EXPENSE_TYPES = ["Capex", "Opex", "Travel", "Professional Services", "Marketing"]
COMPANY_CODES = ["1000", "2000", "3000", "4000"]
ORACLE_ORGS = ["US01", "US02", "EMEA", "APAC", "LATAM", "CANADA"]
ORACLE_DEPTS = [
    ("1100", "Engineering"),
    ("1200", "Sales"),
    ("1300", "Finance"),
    ("1400", "Marketing"),
    ("1500", "Operations"),
    ("1600", "HR"),
    ("1700", "Legal"),
    ("1800", "IT"),
]
COST_CENTER_HIERARCHIES = [
    "Americas > US > West",
    "Americas > US > East",
    "EMEA > UK",
    "EMEA > Germany",
    "APAC > Singapore",
    "APAC > Japan",
]
ACCOUNT_GROUPS = ["COGS", "R&D", "S&M", "G&A", "Infrastructure", "Facilities"]
ACCOUNT_SUB_GROUPS = {
    "COGS": ["Direct Costs", "Indirect Costs"],
    "R&D": ["Engineering Salaries", "Software Licenses", "Cloud Infra"],
    "S&M": ["Salaries", "Advertising", "Events"],
    "G&A": ["Executive", "Finance Ops", "Legal Ops"],
    "Infrastructure": ["AWS", "GCP", "Azure"],
    "Facilities": ["Rent", "Utilities", "Office Supplies"],
}
COST_ELEMENTS = ["Salaries", "Licenses", "Consulting", "Travel", "Hardware", "Hosting", "Office"]
VENDORS = [
    "Amazon Web Services",
    "Salesforce",
    "Zoom Video Communications",
    "Slack Technologies",
    "Stripe",
    "HubSpot",
    "Notion Labs",
    "Figma",
]
JE_SOURCES = ["Manual", "Coupa", "Concur", "Workday", "Oracle", None]
LINE_DESCS = [
    "Monthly SaaS subscription",
    "Professional services - Q1",
    "Cloud infrastructure usage",
    "Software license renewal",
    "Travel reimbursement",
    "Contractor invoice",
    "Marketing campaign spend",
    "Hardware purchase",
    None,
]


def _month_label(month_key: int) -> str:
    year = month_key // 100
    month = month_key % 100
    return datetime(year, month, 1).strftime("%b %Y")


def _last_n_months(n: int) -> list[int]:
    now = datetime.utcnow()
    keys = []
    year, month = now.year, now.month
    for _ in range(n):
        keys.append(year * 100 + month)
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return keys


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_contract_lines()
    _migrate_budget_nc_config()
    _migrate_budget_scenario_status()
    _migrate_budget_audit_view()
    _migrate_spend_activity_id()
    _migrate_account_desc()
    _migrate_account_to_surrogate_key()
    _migrate_project_to_surrogate_key()
    _migrate_spend_account_gaps_view()
    _migrate_spend_department_gaps_view()
    _migrate_spend_activity_gaps_view()
    _migrate_reference_audit_table()
    _migrate_reference_audit_views()
    _migrate_contract_audit_table()
    _migrate_contract_audit_view()
    _migrate_budget_scenario_audit_table()
    _migrate_budget_nc_config_audit_table()
    _seed_db()
    _seed_users()
    _seed_contracts()
    _seed_recurring_contracts()
    _backfill_workday_renewal()
    _seed_budget()
    _seed_reference_data()
    _seed_project_ids()
    _seed_activity_ids()
    _backfill_spend_accounts()
    _backfill_spend_departments()
    _backfill_spend_activities()
    _backfill_account_desc()


def _migrate_budget_scenario_status() -> None:
    """Add status to budget_entries and event_type/changes to budget_entry_audit if missing.
    Also drops legacy wide-column audit fields if they still exist."""
    with engine.connect() as conn:
        for table, col, ddl in [
            ("budget_entries",    "status",     "ENUM('DRAFT','READY_FOR_REVIEW','APPROVED','FINAL','CANCELLED') NOT NULL DEFAULT 'DRAFT'"),
            ("budget_entry_audit","event_type", "VARCHAR(50) NOT NULL DEFAULT 'AMOUNT_CHANGED'"),
            ("budget_entry_audit","changes",    "JSON NOT NULL DEFAULT ('{}')"),
        ]:
            table_exists = conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
            ), {"t": table}).scalar()
            if not table_exists:
                continue
            existing = {
                row[0] for row in conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
                ), {"t": table})
            }
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))

        # Drop legacy wide-column fields from original audit design
        legacy_cols = ["old_q1", "old_q2", "old_q3", "old_q4",
                       "new_q1", "new_q2", "new_q3", "new_q4",
                       "old_status", "new_status"]
        audit_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_entry_audit'"
            ))
        }
        for col in legacy_cols:
            if col in audit_cols:
                conn.execute(text(f"ALTER TABLE budget_entry_audit DROP COLUMN {col}"))

        conn.commit()


def _migrate_budget_nc_config() -> None:
    """Add actuals_cutoff_month_key column to budget_nc_config if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_nc_config'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_nc_config'"
            ))
        }

        if "actuals_cutoff_month_key" not in existing:
            conn.execute(text(
                "ALTER TABLE budget_nc_config ADD COLUMN actuals_cutoff_month_key INT NULL"
            ))
            conn.commit()


def _migrate_budget_audit_view() -> None:
    """Create or replace v_budget_entry_audit — joins budget_entries + budget_scenarios
    + budget_entry_audit and unpacks the changes JSON into named old/new columns."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_budget_entry_audit AS
            SELECT
                bea.id                                                                    AS audit_id,
                be.id                                                                     AS entry_id,
                bs.id                                                                     AS scenario_id,
                bs.name                                                                   AS scenario_name,
                bs.fiscal_year,
                be.department_name,
                be.entry_type,
                bea.event_type,
                bea.changed_by,
                bea.changed_at,

                -- Amount changes (NULL when that field was not part of this event)
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q1_amount.old')) AS DECIMAL(14,2)) AS q1_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q1_amount.new')) AS DECIMAL(14,2)) AS q1_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q2_amount.old')) AS DECIMAL(14,2)) AS q2_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q2_amount.new')) AS DECIMAL(14,2)) AS q2_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q3_amount.old')) AS DECIMAL(14,2)) AS q3_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q3_amount.new')) AS DECIMAL(14,2)) AS q3_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q4_amount.old')) AS DECIMAL(14,2)) AS q4_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q4_amount.new')) AS DECIMAL(14,2)) AS q4_new,

                -- Status change (NULL when this event did not touch status)
                JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.status.old'))                  AS status_old,
                JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.status.new'))                  AS status_new,

                -- Current live state of the entry for reference
                be.q1_amount                                                              AS current_q1,
                be.q2_amount                                                              AS current_q2,
                be.q3_amount                                                              AS current_q3,
                be.q4_amount                                                              AS current_q4,
                be.status                                                                 AS current_status
            FROM budget_entry_audit bea
            JOIN budget_entries be   ON be.id  = bea.entry_id
            JOIN budget_scenarios bs ON bs.id  = be.scenario_id
            ORDER BY bea.changed_at DESC
        """))
        conn.commit()


def _migrate_spend_activity_id() -> None:
    """Add activity_id column to spend table if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spend'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spend'"
            ))
        }

        if "activity_id" not in existing:
            conn.execute(text("ALTER TABLE spend ADD COLUMN activity_id VARCHAR(20) NULL"))
            conn.execute(text("ALTER TABLE spend ADD INDEX ix_spend_activity_id (activity_id)"))
            conn.commit()


def _migrate_spend_account_gaps_view() -> None:
    """Create or replace v_spend_account_gaps — spend oracle_account_numbers with no reference entry."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_spend_account_gaps AS
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
            ORDER BY s.oracle_account_number
        """))
        conn.commit()


def _migrate_spend_department_gaps_view() -> None:
    """Create or replace v_spend_department_gaps — spend oracle_department codes with no reference entry."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_spend_department_gaps AS
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
            ORDER BY s.oracle_department
        """))
        conn.commit()


def _migrate_spend_activity_gaps_view() -> None:
    """Create or replace v_spend_activity_gaps — spend activity_ids with no reference entry."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_spend_activity_gaps AS
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
            ORDER BY s.activity_id
        """))
        conn.commit()


def _migrate_reference_audit_table() -> None:
    """Create reference_audit table if it doesn't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reference_audit (
                id          INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
                table_name  VARCHAR(50)  NOT NULL,
                record_id   VARCHAR(100) NOT NULL,
                event_type  VARCHAR(20)  NOT NULL,
                changes     JSON         NOT NULL,
                changed_by  VARCHAR(255) NOT NULL,
                changed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ref_audit_table (table_name),
                INDEX idx_ref_audit_record (table_name, record_id),
                INDEX idx_ref_audit_at (changed_at)
            )
        """))
        conn.commit()


def _migrate_reference_audit_views() -> None:
    """Create or replace the four per-entity reference audit views."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_reference_audit_departments AS
            SELECT
                ra.id                                                                   AS audit_id,
                ra.record_id                                                            AS department_code,
                d.department_name                                                       AS current_department_name,
                ra.event_type,
                ra.changed_by,
                ra.changed_at,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_name.old'))         AS department_name_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_name.new'))         AS department_name_new
            FROM reference_audit ra
            LEFT JOIN departments d ON d.department_code = ra.record_id
            WHERE ra.table_name = 'departments'
            ORDER BY ra.changed_at DESC
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW v_reference_audit_accounts AS
            SELECT
                ra.id                                                                   AS audit_id,
                ra.record_id                                                            AS account_number,
                an.account_group                                                        AS current_account_group,
                an.account_sub_group                                                    AS current_account_sub_group,
                an.account_desc                                                         AS current_account_desc,
                an.cost_element                                                         AS current_cost_element,
                ra.event_type,
                ra.changed_by,
                ra.changed_at,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_desc.old'))            AS account_desc_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_desc.new'))            AS account_desc_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_group.old'))           AS account_group_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_group.new'))           AS account_group_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_sub_group.old'))       AS account_sub_group_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_sub_group.new'))       AS account_sub_group_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.cost_element.old'))            AS cost_element_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.cost_element.new'))            AS cost_element_new
            FROM reference_audit ra
            LEFT JOIN account_numbers an ON an.account_number = ra.record_id
            WHERE ra.table_name = 'account_numbers'
            ORDER BY ra.changed_at DESC
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW v_reference_audit_projects AS
            SELECT
                ra.id                                                                   AS audit_id,
                ra.record_id                                                            AS project_number,
                p.project_name                                                          AS current_project_name,
                ra.event_type,
                ra.changed_by,
                ra.changed_at,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.project_name.old'))            AS project_name_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.project_name.new'))            AS project_name_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_codes.old'))        AS department_codes_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_codes.new'))        AS department_codes_new
            FROM reference_audit ra
            LEFT JOIN project_ids p ON p.project_number = ra.record_id
            WHERE ra.table_name = 'project_ids'
            ORDER BY ra.changed_at DESC
        """))

        conn.execute(text("""
            CREATE OR REPLACE VIEW v_reference_audit_activities AS
            SELECT
                ra.id                                                                   AS audit_id,
                ra.record_id                                                            AS activity_id,
                ai.activity_id_desc                                                     AS current_activity_id_desc,
                ai.department_code                                                      AS current_department_code,
                d.department_name                                                       AS current_department_name,
                an.account_number                                                       AS current_account_number,
                an.cost_element                                                         AS current_cost_element,
                p.project_number                                                        AS current_project_number,
                p.project_name                                                          AS current_project_name,
                ra.event_type,
                ra.changed_by,
                ra.changed_at,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.activity_id_desc.old'))        AS activity_id_desc_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.activity_id_desc.new'))        AS activity_id_desc_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_code.old'))         AS department_code_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.department_code.new'))         AS department_code_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_id.old'))              AS account_id_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.account_id.new'))              AS account_id_new,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.project_id.old'))              AS project_id_old,
                JSON_UNQUOTE(JSON_EXTRACT(ra.changes, '$.project_id.new'))              AS project_id_new
            FROM reference_audit ra
            LEFT JOIN activity_ids ai  ON ai.activity_id       = ra.record_id
            LEFT JOIN departments d    ON d.department_code    = ai.department_code
            LEFT JOIN account_numbers an ON an.id              = ai.account_id
            LEFT JOIN project_ids p    ON p.id                 = ai.project_id
            WHERE ra.table_name = 'activity_ids'
            ORDER BY ra.changed_at DESC
        """))
        conn.commit()


def _migrate_contract_audit_table() -> None:
    """Create contract_audit table if it doesn't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contract_audit (
                id                    INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
                contract_id           INT          NOT NULL,
                vendor_name           VARCHAR(255) NOT NULL,
                purchase_order_number VARCHAR(100) NOT NULL,
                entity                VARCHAR(20)  NOT NULL,
                entity_id             INT          NOT NULL,
                event_type            VARCHAR(20)  NOT NULL,
                changes               JSON         NOT NULL,
                changed_by            VARCHAR(255) NOT NULL,
                changed_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_contract_audit_contract (contract_id),
                INDEX idx_contract_audit_at (changed_at)
            )
        """))
        conn.commit()


def _migrate_contract_audit_view() -> None:
    """Create or replace the contract audit view with JSON-unpacked change columns."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_contract_audit AS
            SELECT
                ca.id,
                ca.contract_id,
                ca.vendor_name,
                ca.purchase_order_number,
                ca.entity,
                ca.entity_id,
                ca.event_type,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.status.old'))            AS status_old,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.status.new'))            AS status_new,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.period_start.old'))      AS period_start_old,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.period_start.new'))      AS period_start_new,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.period_end.old'))        AS period_end_old,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.period_end.new'))        AS period_end_new,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.entered_amount.old'))    AS entered_amount_old,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.entered_amount.new'))    AS entered_amount_new,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.billing_interval.old'))  AS billing_interval_old,
                JSON_UNQUOTE(JSON_EXTRACT(ca.changes, '$.billing_interval.new'))  AS billing_interval_new,
                ca.changed_by,
                ca.changed_at
            FROM contract_audit ca
            LEFT JOIN contracts c ON c.id = ca.contract_id
        """))
        conn.commit()


def _migrate_budget_scenario_audit_table() -> None:
    """Create budget_scenario_audit table and view if they don't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS budget_scenario_audit (
                id            INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
                scenario_id   INT          NOT NULL,
                fiscal_year   INT          NOT NULL,
                scenario_name VARCHAR(100) NOT NULL,
                event_type    VARCHAR(20)  NOT NULL,
                changes       JSON         NOT NULL,
                changed_by    VARCHAR(255) NOT NULL,
                changed_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bsa_scenario (scenario_id),
                INDEX idx_bsa_fy (fiscal_year),
                INDEX idx_bsa_at (changed_at)
            )
        """))
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_budget_scenario_audit AS
            SELECT
                bsa.id,
                bsa.scenario_id,
                bsa.fiscal_year,
                bsa.scenario_name,
                bsa.event_type,
                JSON_UNQUOTE(JSON_EXTRACT(bsa.changes, '$.name.old'))        AS name_old,
                JSON_UNQUOTE(JSON_EXTRACT(bsa.changes, '$.name.new'))        AS name_new,
                JSON_UNQUOTE(JSON_EXTRACT(bsa.changes, '$.description.old')) AS description_old,
                JSON_UNQUOTE(JSON_EXTRACT(bsa.changes, '$.description.new')) AS description_new,
                bsa.changed_by,
                bsa.changed_at
            FROM budget_scenario_audit bsa
            LEFT JOIN budget_scenarios bs ON bs.id = bsa.scenario_id
        """))
        conn.commit()


def _migrate_budget_nc_config_audit_table() -> None:
    """Create budget_nc_config_audit table and view if they don't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS budget_nc_config_audit (
                id          INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
                fiscal_year INT          NOT NULL,
                event_type  VARCHAR(20)  NOT NULL,
                changes     JSON         NOT NULL,
                changed_by  VARCHAR(255) NOT NULL,
                changed_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bnca_fy (fiscal_year),
                INDEX idx_bnca_at (changed_at)
            )
        """))
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_budget_nc_config_audit AS
            SELECT
                id,
                fiscal_year,
                event_type,
                JSON_UNQUOTE(JSON_EXTRACT(changes, '$.actuals_cutoff_month_key.old')) AS cutoff_old,
                JSON_UNQUOTE(JSON_EXTRACT(changes, '$.actuals_cutoff_month_key.new')) AS cutoff_new,
                changed_by,
                changed_at
            FROM budget_nc_config_audit
        """))
        conn.commit()


def _migrate_account_to_surrogate_key() -> None:
    """Migrate account_numbers from string PK to integer surrogate PK (idempotent).

    Detects migration need by checking for 'id' column on account_numbers.
    Handles the FK on activity_ids.account_number → replaces with account_id INT FK.
    """
    with engine.connect() as conn:
        acct_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'account_numbers'"
            ))
        }
        if "id" in acct_cols:
            return  # already migrated

        act_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'"
            ))
        }

        # 1. Add nullable id column to account_numbers
        conn.execute(text("ALTER TABLE account_numbers ADD COLUMN id INT NULL"))

        # 2. Assign sequential ids to existing rows
        rows = conn.execute(text(
            "SELECT account_number FROM account_numbers ORDER BY account_number"
        )).fetchall()
        for i, (acct_num,) in enumerate(rows, 1):
            conn.execute(text(
                "UPDATE account_numbers SET id = :i WHERE account_number = :an"
            ), {"i": i, "an": acct_num})

        # 3. Add account_id column to activity_ids and backfill from join
        if "account_id" not in act_cols:
            conn.execute(text("ALTER TABLE activity_ids ADD COLUMN account_id INT NULL"))
            if "account_number" in act_cols:
                conn.execute(text("""
                    UPDATE activity_ids ai
                    JOIN account_numbers an ON ai.account_number = an.account_number
                    SET ai.account_id = an.id
                    WHERE ai.account_number IS NOT NULL
                """))

        # 4. Drop FK from activity_ids.account_number → account_numbers
        fk_rows = conn.execute(text("""
            SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'
              AND COLUMN_NAME = 'account_number' AND REFERENCED_TABLE_NAME = 'account_numbers'
        """)).fetchall()
        for (fk_name,) in fk_rows:
            conn.execute(text(f"ALTER TABLE activity_ids DROP FOREIGN KEY `{fk_name}`"))

        # 5. Drop account_number index + column from activity_ids
        if "account_number" in act_cols:
            idx_rows = conn.execute(text("""
                SELECT DISTINCT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'
                  AND COLUMN_NAME = 'account_number' AND INDEX_NAME != 'PRIMARY'
            """)).fetchall()
            for (idx_name,) in idx_rows:
                conn.execute(text(f"ALTER TABLE activity_ids DROP INDEX `{idx_name}`"))
            conn.execute(text("ALTER TABLE activity_ids DROP COLUMN account_number"))

        # 6. Add index on activity_ids.account_id
        conn.execute(text(
            "CREATE INDEX ix_activity_ids_account_id ON activity_ids (account_id)"
        ))

        # 7. Drop old string PK on account_numbers and promote id as PK + AUTO_INCREMENT
        conn.execute(text("ALTER TABLE account_numbers MODIFY COLUMN id INT NOT NULL"))
        conn.execute(text("ALTER TABLE account_numbers DROP PRIMARY KEY"))
        conn.execute(text(
            "ALTER TABLE account_numbers MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT, "
            "ADD PRIMARY KEY (id)"
        ))

        # 8. Rewrite account_number values to ACC-{id:04d} format
        all_rows = conn.execute(text(
            "SELECT id, account_number FROM account_numbers"
        )).fetchall()
        for (acct_id, _) in all_rows:
            conn.execute(text(
                "UPDATE account_numbers SET account_number = :code WHERE id = :id"
            ), {"code": f"ACC-{acct_id:04d}", "id": acct_id})

        # 9. Add UNIQUE constraint on account_number and new FK from activity_ids
        conn.execute(text(
            "ALTER TABLE account_numbers ADD UNIQUE KEY uq_account_number (account_number)"
        ))
        conn.execute(text("""
            ALTER TABLE activity_ids
            ADD CONSTRAINT fk_activity_account_id
            FOREIGN KEY (account_id) REFERENCES account_numbers(id) ON DELETE SET NULL
        """))

        conn.commit()


def _migrate_project_to_surrogate_key() -> None:
    """Convert project_ids from string PK to integer surrogate PK. Fully resumable/idempotent."""
    with engine.connect() as conn:
        if not conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_ids'"
        )).scalar_one():
            return

        def pi_cols():
            return {r[0] for r in conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_ids'"
            ))}

        # Done when old string PK column is gone
        if 'project_id' not in pi_cols():
            return

        # Step 1: Add new columns (idempotent)
        existing = pi_cols()
        for col, ddl in [
            ('id',             "ALTER TABLE project_ids ADD COLUMN id INT NULL"),
            ('project_number', "ALTER TABLE project_ids ADD COLUMN project_number VARCHAR(20) NULL"),
            ('project_name',   "ALTER TABLE project_ids ADD COLUMN project_name VARCHAR(100) NULL"),
        ]:
            if col not in existing:
                conn.execute(text(ddl))
        conn.commit()

        # Step 2: Populate if any rows still have id = NULL
        if conn.execute(text("SELECT COUNT(*) FROM project_ids WHERE id IS NULL")).scalar_one():
            conn.execute(text("SET @row := 0"))
            conn.execute(text("UPDATE project_ids SET id = (@row := @row + 1) ORDER BY project_id"))
            conn.execute(text(
                "UPDATE project_ids "
                "SET project_number = CONCAT('PRJ-', LPAD(id, 4, '0')), project_name = project_id "
                "WHERE project_number IS NULL"
            ))
            conn.commit()

        # Step 3: Migrate project_departments string FK → int FK
        pd_project_id_type = conn.execute(text(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_departments' "
            "AND COLUMN_NAME = 'project_id'"
        )).scalar()
        if pd_project_id_type == 'varchar':
            pd_cols = {r[0] for r in conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_departments'"
            ))}
            if 'new_project_id' not in pd_cols:
                conn.execute(text("ALTER TABLE project_departments ADD COLUMN new_project_id INT NULL"))
            conn.execute(text("""
                UPDATE project_departments pd
                JOIN project_ids pi ON pd.project_id = pi.project_id
                SET pd.new_project_id = pi.id WHERE pd.new_project_id IS NULL
            """))
            # Drop FK before PK — InnoDB requires the PK as an index backing the FK,
            # so we must remove the FK constraint first or we get error 1553.
            fk_pd = conn.execute(text("""
                SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_departments'
                AND COLUMN_NAME = 'project_id' AND REFERENCED_TABLE_NAME = 'project_ids'
            """)).scalar()
            if fk_pd:
                conn.execute(text(f"ALTER TABLE project_departments DROP FOREIGN KEY `{fk_pd}`"))
            conn.execute(text("ALTER TABLE project_departments DROP PRIMARY KEY"))
            conn.execute(text("ALTER TABLE project_departments DROP COLUMN project_id"))
            conn.execute(text("ALTER TABLE project_departments RENAME COLUMN new_project_id TO project_id"))
            conn.execute(text("ALTER TABLE project_departments ADD PRIMARY KEY (project_id, department_code)"))
            conn.commit()

        # Step 4: Migrate activity_ids.project_id string FK → int FK
        ai_project_id_type = conn.execute(text(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids' "
            "AND COLUMN_NAME = 'project_id'"
        )).scalar()
        if ai_project_id_type == 'varchar':
            ai_cols = {r[0] for r in conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'"
            ))}
            if 'new_project_id' not in ai_cols:
                conn.execute(text("ALTER TABLE activity_ids ADD COLUMN new_project_id INT NULL"))
            conn.execute(text("""
                UPDATE activity_ids ai
                JOIN project_ids pi ON ai.project_id = pi.project_id
                SET ai.new_project_id = pi.id
                WHERE ai.project_id IS NOT NULL AND ai.new_project_id IS NULL
            """))
            fk_ai = conn.execute(text("""
                SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'
                AND COLUMN_NAME = 'project_id' AND REFERENCED_TABLE_NAME = 'project_ids'
            """)).scalar()
            idx_ai = conn.execute(text("""
                SELECT INDEX_NAME FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'
                AND COLUMN_NAME = 'project_id' AND INDEX_NAME != 'PRIMARY' LIMIT 1
            """)).scalar()
            if fk_ai:
                conn.execute(text(f"ALTER TABLE activity_ids DROP FOREIGN KEY `{fk_ai}`"))
            if idx_ai:
                conn.execute(text(f"ALTER TABLE activity_ids DROP INDEX `{idx_ai}`"))
            conn.execute(text("ALTER TABLE activity_ids DROP COLUMN project_id"))
            conn.execute(text("ALTER TABLE activity_ids RENAME COLUMN new_project_id TO project_id"))
            conn.execute(text("ALTER TABLE activity_ids ADD INDEX ix_activity_ids_project_id (project_id)"))
            conn.commit()

        # Step 5: Fix project_ids — drop old string PK + desc, promote int id as PK
        cur = pi_cols()
        conn.execute(text("ALTER TABLE project_ids DROP PRIMARY KEY"))
        conn.execute(text("ALTER TABLE project_ids DROP COLUMN project_id"))
        if 'project_id_desc' in cur:
            conn.execute(text("ALTER TABLE project_ids DROP COLUMN project_id_desc"))
        conn.execute(text(
            "ALTER TABLE project_ids MODIFY COLUMN id INT NOT NULL AUTO_INCREMENT, ADD PRIMARY KEY (id)"
        ))
        conn.execute(text("ALTER TABLE project_ids MODIFY COLUMN project_number VARCHAR(20) NOT NULL"))
        if not conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_ids' "
            "AND CONSTRAINT_NAME = 'uq_project_number'"
        )).scalar_one():
            conn.execute(text("ALTER TABLE project_ids ADD UNIQUE KEY uq_project_number (project_number)"))
        conn.execute(text("ALTER TABLE project_ids MODIFY COLUMN project_name VARCHAR(100) NOT NULL"))
        conn.commit()

        # Step 6: Re-add FK constraints (check before adding)
        if not conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'project_departments'
            AND COLUMN_NAME = 'project_id' AND REFERENCED_TABLE_NAME = 'project_ids'
        """)).scalar_one():
            conn.execute(text("""
                ALTER TABLE project_departments ADD CONSTRAINT fk_pd_project_id
                FOREIGN KEY (project_id) REFERENCES project_ids (id) ON DELETE CASCADE
            """))
        if not conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activity_ids'
            AND COLUMN_NAME = 'project_id' AND REFERENCED_TABLE_NAME = 'project_ids'
        """)).scalar_one():
            conn.execute(text("""
                ALTER TABLE activity_ids ADD CONSTRAINT fk_ai_project_id
                FOREIGN KEY (project_id) REFERENCES project_ids (id) ON DELETE SET NULL
            """))
        conn.commit()


def _migrate_account_desc() -> None:
    """Add account_desc column to account_numbers table if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'account_numbers'"
        )).scalar()
        if not table_exists:
            return
        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'account_numbers'"
            ))
        }
        if "account_desc" not in existing:
            conn.execute(text("ALTER TABLE account_numbers ADD COLUMN account_desc VARCHAR(255) NULL"))
            conn.commit()


def _migrate_contract_lines() -> None:
    """Add billing_interval and entered_amount columns if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        # No-op if table doesn't exist yet — create_all will build it with all columns
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contract_lines'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contract_lines'"
            ))
        }

        if "billing_interval" not in existing:
            conn.execute(text(
                "ALTER TABLE contract_lines ADD COLUMN billing_interval "
                "ENUM('monthly','quarterly','yearly','custom') NOT NULL DEFAULT 'monthly'"
            ))
        if "entered_amount" not in existing:
            conn.execute(text(
                "ALTER TABLE contract_lines ADD COLUMN entered_amount DECIMAL(14,2)"
            ))
            conn.execute(text(
                "UPDATE contract_lines SET entered_amount = monthly_amount WHERE entered_amount IS NULL"
            ))
        conn.commit()


def _seed_users() -> None:
    from src.models.user import User, UserRole
    from src.core.security import hash_password

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(User)).scalar_one()
        if count > 0:
            return

        seed_users = [
            User(email="admin@example.com",         full_name="Admin User",         role=UserRole.ADMIN,         hashed_password=hash_password("admin123"),         is_active=True),
            User(email="bizadmin@example.com",       full_name="Biz Admin User",     role=UserRole.BIZ_ADMIN,     hashed_password=hash_password("bizadmin123"),     is_active=True),
            User(email="serviceowner@example.com",   full_name="Service Owner User", role=UserRole.SERVICE_OWNER, hashed_password=hash_password("serviceowner123"), is_active=True),
            User(email="readonly@example.com",       full_name="Read Only User",     role=UserRole.READ_ONLY,     hashed_password=hash_password("readonly123"),     is_active=True),
        ]
        db.add_all(seed_users)
        db.commit()
    finally:
        db.close()


def _seed_db() -> None:
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(Spend)).scalar_one()
        if count > 0:
            return

        month_keys = _last_n_months(6)
        rows = []
        for i in range(150):
            dept_code, dept_name = random.choice(ORACLE_DEPTS)
            acct_group = random.choice(ACCOUNT_GROUPS)
            acct_sub_group = random.choice(ACCOUNT_SUB_GROUPS[acct_group])
            mk = random.choice(month_keys)
            po_num = f"PO-{random.randint(10000, 99999)}" if random.random() > 0.4 else None
            inv_num = f"INV-{random.randint(10000, 99999)}" if random.random() > 0.3 else None

            rows.append(
                Spend(
                    month_key=mk,
                    month_label=_month_label(mk),
                    expense_type=random.choice(EXPENSE_TYPES),
                    company_code=random.choice(COMPANY_CODES),
                    oracle_organization=random.choice(ORACLE_ORGS),
                    oracle_account_number=f"ACC-{random.randint(1000, 9999)}",
                    oracle_department=dept_code,
                    oracle_department_name=dept_name,
                    oracle_cost_center_hierarchy=random.choice(COST_CENTER_HIERARCHIES),
                    oracle_account_group=acct_group,
                    oracle_account_sub_group=acct_sub_group,
                    oracle_cost_element=random.choice(COST_ELEMENTS),
                    line_desc=random.choice(LINE_DESCS),
                    vendor_name=random.choice(VENDORS),
                    po_recon=po_num,
                    po_description=f"Purchase order for {acct_sub_group}" if po_num else None,
                    purchase_order_number=po_num,
                    purchase_order_line_number=str(random.randint(1, 5)) if po_num else None,
                    invoice_number=inv_num,
                    invoice_line_number=str(random.randint(1, 10)) if inv_num else None,
                    je_source=random.choice(JE_SOURCES),
                    amount_usd=Decimal(str(round(random.uniform(50, 100000), 2))),
                )
            )

        db.add_all(rows)
        db.commit()
    finally:
        db.close()


def _seed_contracts() -> None:
    from src.models.contract import Contract, ContractLine, ContractStatus, BillingInterval
    from src.schemas.contract import compute_monthly_amount

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(Contract)).scalar_one()
        if count > 0:
            return

        seed_data = [
            # Monthly billing — entered_amount IS the monthly rate
            {
                "vendor_name": "Salesforce",
                "description": "Enterprise CRM platform — 3-year site license",
                "oracle_department": "1200",
                "oracle_department_name": "Sales",
                "oracle_account_number": "ACC-6385",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-83353",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 4, "period_start": date(2026, 5, 1), "period_end": date(2027, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("67888.29")},
                    {"po_line_number": 5, "period_start": date(2027, 5, 1), "period_end": date(2028, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("68888.29")},
                    {"po_line_number": 6, "period_start": date(2028, 5, 1), "period_end": date(2029, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("69888.29")},
                ],
            },
            # Quarterly billing — entered_amount is per-quarter; monthly = /3
            {
                "vendor_name": "GitHub",
                "description": "Enterprise source control & CI/CD — 2-year contract",
                "oracle_department": "1100",
                "oracle_department_name": "Engineering",
                "oracle_account_number": "ACC-6401",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-91200",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2026, 1, 1), "period_end": date(2026, 12, 31), "billing_interval": BillingInterval.QUARTERLY, "entered_amount": Decimal("37500.00")},
                    {"po_line_number": 2, "period_start": date(2027, 1, 1), "period_end": date(2027, 12, 31), "billing_interval": BillingInterval.QUARTERLY, "entered_amount": Decimal("39000.00")},
                ],
            },
            # Yearly billing — entered_amount is the annual fee; monthly = /12
            {
                "vendor_name": "Workday",
                "description": "HR & Finance SaaS platform — annual renewal",
                "oracle_department": "1600",
                "oracle_department_name": "HR",
                "oracle_account_number": "ACC-5510",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-77040",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2026, 4, 1), "period_end": date(2027, 3, 31), "billing_interval": BillingInterval.YEARLY, "entered_amount": Decimal("264000.00")},
                ],
            },
            # Custom billing — entered_amount is the total for the full period; monthly = total / months
            {
                "vendor_name": "Tableau",
                "description": "BI & analytics platform — expired 3-year deal",
                "oracle_department": "1300",
                "oracle_department_name": "Finance",
                "oracle_account_number": "ACC-6110",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-60301",
                "status": ContractStatus.EXPIRED,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2023, 1, 1), "period_end": date(2023, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("100800.00")},
                    {"po_line_number": 2, "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("104400.00")},
                    {"po_line_number": 3, "period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("108000.00")},
                ],
            },
        ]

        for item in seed_data:
            lines_data = item.pop("lines")
            contract = Contract(**item)
            for ld in lines_data:
                line = ContractLine(**ld)
                line.monthly_amount = compute_monthly_amount(
                    line.entered_amount, line.billing_interval, line.period_start, line.period_end
                )
                contract.lines.append(line)
            db.add(contract)

        db.commit()
    finally:
        db.close()


def _seed_recurring_contracts() -> None:
    """Seed ACTIVE contracts for recurring spend vendors that have no contract yet.

    Queries spend for vendor+dimension combos with 2+ months of data (among vendors with
    3+ rows total), then inserts one contract per missing vendor+account_number pair with
    a single MONTHLY line from first-spend-month through Dec 31 2027.  Idempotent.
    """
    from src.models.contract import Contract, ContractLine, ContractStatus, BillingInterval
    from src.models.spend import Spend
    from src.schemas.contract import compute_monthly_amount

    db = SessionLocal()
    try:
        spend_count = db.execute(select(func.count()).select_from(Spend)).scalar_one()
        if spend_count == 0:
            return

        rows = db.execute(text("""
            SELECT
                vendor_name,
                oracle_department,
                oracle_department_name,
                oracle_account_number,
                oracle_account_sub_group,
                oracle_account_group,
                COUNT(*)                    AS month_count,
                MIN(month_key)              AS first_month,
                ROUND(AVG(amount_usd), 2)  AS avg_monthly
            FROM spend
            WHERE vendor_name NOT LIKE 'Internal%%'
            GROUP BY
                vendor_name, oracle_department, oracle_department_name,
                oracle_account_number, oracle_account_sub_group, oracle_account_group
            HAVING month_count >= 2
              AND vendor_name IN (
                  SELECT vendor_name FROM spend GROUP BY vendor_name HAVING COUNT(*) >= 3
              )
            ORDER BY vendor_name, month_count DESC
        """)).fetchall()

        po_counter = 1
        # Pass 1: insert contracts for stable combos (2+ months same dimension).
        # AT&T gets two contracts (wireless + internet) — both are genuine recurring.
        for row in rows:
            vendor_name      = row[0]
            oracle_dept      = row[1]
            oracle_dept_name = row[2]
            account_number   = row[3]
            sub_group        = row[4]
            first_month_int  = row[7]
            avg_monthly      = Decimal(str(row[8]))

            existing = db.query(Contract).filter(
                Contract.vendor_name == vendor_name,
                Contract.oracle_account_number == account_number,
            ).first()
            if existing:
                continue

            ym = str(first_month_int)
            period_start = date(int(ym[:4]), int(ym[4:]), 1)
            period_end   = date(2027, 12, 31)

            contract = Contract(
                vendor_name=vendor_name,
                oracle_department=oracle_dept,
                oracle_department_name=oracle_dept_name,
                oracle_account_number=account_number,
                oracle_account_sub_group=sub_group,
                purchase_order_number=f"PO-REC-{po_counter:04d}",
                status=ContractStatus.ACTIVE,
            )
            line = ContractLine(
                po_line_number=1,
                period_start=period_start,
                period_end=period_end,
                billing_interval=BillingInterval.MONTHLY,
                entered_amount=avg_monthly,
            )
            line.monthly_amount = compute_monthly_amount(
                line.entered_amount, line.billing_interval, line.period_start, line.period_end
            )
            contract.lines.append(line)
            db.add(contract)
            po_counter += 1

        db.flush()

        # Pass 2: for recurring vendors with no contract at all yet, pick their dominant dimension.
        still_missing = db.execute(text("""
            SELECT
                vendor_name,
                oracle_department,
                oracle_department_name,
                oracle_account_number,
                oracle_account_sub_group,
                oracle_account_group,
                COUNT(*)                    AS dim_count,
                MIN(month_key)              AS first_month,
                ROUND(AVG(amount_usd), 2)  AS avg_monthly
            FROM spend
            WHERE vendor_name NOT LIKE 'Internal%%'
              AND vendor_name IN (
                  SELECT vendor_name FROM spend GROUP BY vendor_name HAVING COUNT(*) >= 3
              )
              AND vendor_name NOT IN (SELECT DISTINCT vendor_name FROM contracts)
            GROUP BY
                vendor_name, oracle_department, oracle_department_name,
                oracle_account_number, oracle_account_sub_group, oracle_account_group
            ORDER BY vendor_name, dim_count DESC
        """)).fetchall()

        seen_vendor: set[str] = set()
        for row in still_missing:
            vendor_name = row[0]
            if vendor_name in seen_vendor:
                continue  # already queued a contract for this vendor in pass 2
            seen_vendor.add(vendor_name)

            account_number   = row[3]
            oracle_dept      = row[1]
            oracle_dept_name = row[2]
            sub_group        = row[4]
            first_month_int  = row[7]
            avg_monthly      = Decimal(str(row[8]))

            ym = str(first_month_int)
            period_start = date(int(ym[:4]), int(ym[4:]), 1)
            period_end   = date(2027, 12, 31)

            contract = Contract(
                vendor_name=vendor_name,
                oracle_department=oracle_dept,
                oracle_department_name=oracle_dept_name,
                oracle_account_number=account_number,
                oracle_account_sub_group=sub_group,
                purchase_order_number=f"PO-REC-{po_counter:04d}",
                status=ContractStatus.ACTIVE,
            )
            line = ContractLine(
                po_line_number=1,
                period_start=period_start,
                period_end=period_end,
                billing_interval=BillingInterval.MONTHLY,
                entered_amount=avg_monthly,
            )
            line.monthly_amount = compute_monthly_amount(
                line.entered_amount, line.billing_interval, line.period_start, line.period_end
            )
            contract.lines.append(line)
            db.add(contract)
            po_counter += 1

        db.commit()
    finally:
        db.close()


def _backfill_workday_renewal() -> None:
    """Add a renewal line to the Workday contract covering Apr 2027 – Dec 2027 if missing."""
    from src.models.contract import Contract, ContractLine, BillingInterval
    from src.schemas.contract import compute_monthly_amount

    db = SessionLocal()
    try:
        workday = db.query(Contract).filter(Contract.vendor_name == "Workday").first()
        if not workday:
            return

        has_coverage = any(
            cl.period_end >= date(2027, 12, 1) for cl in workday.lines
        )
        if has_coverage:
            return

        renewal = ContractLine(
            contract_id=workday.id,
            po_line_number=2,
            period_start=date(2027, 4, 1),
            period_end=date(2027, 12, 31),
            billing_interval=BillingInterval.MONTHLY,
            entered_amount=Decimal("22000.00"),
        )
        renewal.monthly_amount = compute_monthly_amount(
            renewal.entered_amount, renewal.billing_interval, renewal.period_start, renewal.period_end
        )
        db.add(renewal)
        db.commit()
    finally:
        db.close()


def _seed_budget() -> None:
    from src.models.budget import BudgetScenario, BudgetEntry, BudgetNcConfig

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(BudgetScenario)).scalar_one()
        if count > 0:
            return

        fiscal_year = 2027

        cfg = BudgetNcConfig(
            fiscal_year=fiscal_year,
            selected_cost_elements=["Salaries", "Travel"],
            updated_by="admin@example.com",
        )
        db.add(cfg)

        baseline = BudgetScenario(
            name="Baseline FY2027",
            description="Default baseline budget plan for FY2027",
            fiscal_year=fiscal_year,
            budget_type="NON_CONTROLLABLE",
            is_baseline=True,
            created_by="admin@example.com",
        )
        db.add(baseline)

        db.flush()

        dept_approved_recs = {
            "Engineering":   (Decimal("185000"), Decimal("185000"), Decimal("190000"), Decimal("195000")),
            "Sales":         (Decimal("120000"), Decimal("125000"), Decimal("125000"), Decimal("130000")),
            "Finance":       (Decimal("75000"),  Decimal("75000"),  Decimal("78000"),  Decimal("78000")),
            "Marketing":     (Decimal("90000"),  Decimal("95000"),  Decimal("95000"),  Decimal("100000")),
            "Operations":    (Decimal("60000"),  Decimal("60000"),  Decimal("62000"),  Decimal("62000")),
            "HR":            (Decimal("45000"),  Decimal("45000"),  Decimal("47000"),  Decimal("47000")),
            "Legal":         (Decimal("38000"),  Decimal("38000"),  Decimal("40000"),  Decimal("40000")),
            "IT":            (Decimal("55000"),  Decimal("55000"),  Decimal("57000"),  Decimal("57000")),
        }
        dept_additional_asks = {
            "Engineering":   (Decimal("15000"), Decimal("15000"), Decimal("20000"), Decimal("20000")),
            "Sales":         (Decimal("10000"), Decimal("10000"), Decimal("12000"), Decimal("12000")),
            "Finance":       (Decimal("5000"),  Decimal("5000"),  Decimal("5000"),  Decimal("5000")),
            "Marketing":     (Decimal("8000"),  Decimal("8000"),  Decimal("10000"), Decimal("10000")),
            "Operations":    (None,             None,             None,             None),
            "HR":            (Decimal("3000"),  Decimal("3000"),  Decimal("3000"),  Decimal("3000")),
            "Legal":         (None,             None,             None,             None),
            "IT":            (Decimal("4000"),  Decimal("4000"),  Decimal("5000"),  Decimal("5000")),
        }

        for dept, (q1, q2, q3, q4) in dept_approved_recs.items():
            db.add(BudgetEntry(
                scenario_id=baseline.id,
                department_name=dept,
                entry_type="APPROVED_REC",
                q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
                created_by="admin@example.com",
            ))

        for dept, (q1, q2, q3, q4) in dept_additional_asks.items():
            if any(x is not None for x in (q1, q2, q3, q4)):
                db.add(BudgetEntry(
                    scenario_id=baseline.id,
                    department_name=dept,
                    entry_type="ADDITIONAL_ASK",
                    q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
                    created_by="admin@example.com",
                ))

        db.commit()
    finally:
        db.close()


def _seed_reference_data() -> None:
    from src.models.reference import AccountNumber, Department
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        dept_count = db.execute(select(func.count()).select_from(Department)).scalar_one()
        if dept_count == 0:
            for code, name in ORACLE_DEPTS:
                db.add(Department(department_code=code, department_name=name))
            db.commit()

        acct_count = db.execute(select(func.count()).select_from(AccountNumber)).scalar_one()
        if acct_count == 0:
            rows = db.execute(
                select(
                    Spend.oracle_account_number,
                    Spend.oracle_account_group,
                    Spend.oracle_account_sub_group,
                    Spend.oracle_cost_element,
                ).distinct()
            ).all()
            seen: set[str] = set()
            for row in rows:
                acct_num, acct_group, acct_sub, cost_elem = row[0], row[1], row[2], row[3]
                if acct_num and acct_num not in seen:
                    seen.add(acct_num)
                    db.add(AccountNumber(
                        account_number=acct_num,
                        account_desc=_build_account_desc(acct_group, acct_sub, cost_elem),
                        account_group=acct_group,
                        account_sub_group=acct_sub,
                        cost_element=cost_elem,
                    ))
            db.commit()
    finally:
        db.close()


def _build_account_desc(account_group: str | None, account_sub_group: str | None, cost_element: str | None) -> str | None:
    """Generate a human-readable description from account fields.
    Format: "<sub_group> — <account_group> / <cost_element>"
    Examples: "Engineering Salaries — R&D / Salaries", "AWS — Infrastructure / Hosting"
    """
    if account_sub_group and account_group and cost_element:
        return f"{account_sub_group} — {account_group} / {cost_element}"
    if account_sub_group and account_group:
        return f"{account_sub_group} — {account_group}"
    if account_sub_group:
        return account_sub_group
    if account_group and cost_element:
        return f"{account_group} / {cost_element}"
    return account_group


def _assign_project(expense_type: str | None, account_group: str | None, account_sub_group: str | None) -> str | None:
    """Map a spend row's expense_type + account_group + sub_group to a project_id."""
    ag = (account_group or "").strip()
    sg = (account_sub_group or "").strip()
    et = (expense_type or "").strip().upper()

    if et == "CAPEX":
        if "Network" in sg:
            return "CAPEX-NET-INFRA"
        if any(k in sg for k in ("Computer", "Peripheral", "Personal Computer")):
            return "CAPEX-COMPUTE"
        if "Software" in sg:
            return "CAPEX-SOFTWARE"
        if ag == "Data Services":
            return "CAPEX-DC"
        return "CAPEX-MISC"

    # OPEX (and anything else)
    if ag in ("Labor", "Staff Related Expenses"):
        return "OPEX-LABOR"
    if ag == "Data Services":
        if any(k in sg for k in ("DC Power", "DC Rent", "DC Professional Services", "DC Services")):
            return "OPEX-DC-OPS"
        return "OPEX-CLOUD"
    if ag in ("Equipment & Software Expense",):
        return "OPEX-SAAS"
    if ag in ("Contract & Professional Services", "Temporary & Consulting"):
        return "OPEX-CONSULTING"
    if ag == "Telephone & Related":
        return "OPEX-TELECOM"
    return "OPEX-G-AND-A"


def _seed_project_ids() -> None:
    from src.models.reference import ProjectId, Department

    db = SessionLocal()
    try:
        if db.execute(select(func.count()).select_from(ProjectId)).scalar_one() > 0:
            return

        all_depts = {d.department_code: d for d in db.query(Department).all()}

        def depts(*codes):
            return [all_depts[c] for c in codes if c in all_depts]

        project_names = [
            ("CAPEX-NET-INFRA", depts("1100", "1200", "1600", "1700", "1800")),
            ("CAPEX-COMPUTE",   depts("1100", "1200", "1300", "1700", "1800")),
            ("CAPEX-SOFTWARE",  depts("1100", "1200", "1300", "1400", "1600", "1800")),
            ("CAPEX-DC",        depts("1100", "1500")),
            ("CAPEX-MISC",      depts("1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800")),
            ("OPEX-DC-OPS",     depts("1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800")),
            ("OPEX-CLOUD",      depts("1100", "1200", "1400", "1500", "1800")),
            ("OPEX-SAAS",       depts("1100", "1300", "1400", "1500", "1600", "1800")),
            ("OPEX-LABOR",      depts("1100", "1200", "1300", "1500", "1600", "1800")),
            ("OPEX-CONSULTING", depts("1100", "1200", "1300", "1500", "1600", "1700")),
            ("OPEX-TELECOM",    depts("1100", "1300", "1500", "1800")),
            ("OPEX-G-AND-A",    depts("1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800")),
        ]
        for name, dept_list in project_names:
            proj = ProjectId(project_number="__TEMP__", project_name=name, departments=dept_list)
            db.add(proj)
            db.flush()
            proj.project_number = f"PRJ-{proj.id:04d}"
        db.commit()
    finally:
        db.close()


def _seed_activity_ids() -> None:
    from src.models.reference import ActivityId, AccountNumber, ProjectId
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        if db.execute(select(func.count()).select_from(ActivityId)).scalar_one() > 0:
            return

        acct_map = {a.account_number: a.id for a in db.query(AccountNumber).all()}
        proj_map = {p.project_name: p.id for p in db.query(ProjectId).all()}

        rows = db.execute(text("""
            SELECT
                activity_id,
                oracle_department,
                oracle_department_name,
                oracle_account_number,
                expense_type,
                oracle_account_group,
                oracle_account_sub_group,
                COUNT(*) AS cnt
            FROM spend
            WHERE activity_id IS NOT NULL
            GROUP BY activity_id, oracle_department, oracle_account_number,
                     expense_type, oracle_account_group, oracle_account_sub_group,
                     oracle_department_name
            ORDER BY activity_id, cnt DESC
        """)).fetchall()

        seen: set[str] = set()
        for row in rows:
            act_id = row[0]
            if act_id in seen:
                continue
            seen.add(act_id)
            dept_code    = row[1]
            acct_num     = row[3]
            expense_type = row[4]
            acct_group   = row[5]
            acct_sub     = row[6]

            desc = f"{acct_group} / {acct_sub}" if acct_sub else acct_group
            project_name = _assign_project(expense_type, acct_group, acct_sub)
            db.add(ActivityId(
                activity_id=act_id,
                activity_id_desc=desc,
                department_code=dept_code,
                account_id=acct_map.get(acct_num),
                project_id=proj_map.get(project_name),
            ))
        db.commit()
    finally:
        db.close()


def _backfill_spend_activities() -> None:
    """Add any activity_id values from spend not yet in the activity_ids reference table (idempotent)."""
    from src.models.reference import ActivityId, AccountNumber, ProjectId
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        existing = {a.activity_id for a in db.query(ActivityId.activity_id).all()}
        acct_map = {a.account_number: a.id for a in db.query(AccountNumber).all()}
        proj_map = {p.project_name: p.id for p in db.query(ProjectId).all()}

        rows = db.execute(text("""
            SELECT
                activity_id,
                oracle_department,
                oracle_account_number,
                expense_type,
                oracle_account_group,
                oracle_account_sub_group,
                COUNT(*) AS cnt
            FROM spend
            WHERE activity_id IS NOT NULL
            GROUP BY activity_id, oracle_department, oracle_account_number,
                     expense_type, oracle_account_group, oracle_account_sub_group
            ORDER BY activity_id, cnt DESC
        """)).fetchall()

        seen: set[str] = set()
        added = False
        for row in rows:
            act_id = row[0]
            if act_id in existing or act_id in seen:
                continue
            seen.add(act_id)
            dept_code    = row[1]
            acct_num     = row[2]
            expense_type = row[3]
            acct_group   = row[4]
            acct_sub     = row[5]

            desc = f"{acct_group} / {acct_sub}" if acct_sub else acct_group
            project_name = _assign_project(expense_type, acct_group, acct_sub)
            db.add(ActivityId(
                activity_id=act_id,
                activity_id_desc=desc,
                department_code=dept_code,
                account_id=acct_map.get(acct_num),
                project_id=proj_map.get(project_name),
            ))
            added = True
        if added:
            db.commit()
    finally:
        db.close()


def _backfill_spend_departments() -> None:
    """Add any oracle_department codes from spend that are missing from departments (idempotent)."""
    from src.models.reference import Department
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        existing = {d.department_code for d in db.query(Department.department_code).all()}
        rows = db.execute(
            select(Spend.oracle_department, Spend.oracle_department_name).distinct()
        ).all()
        seen: set[str] = set()
        added = False
        for dept_code, dept_name in rows:
            if dept_code and dept_code not in existing and dept_code not in seen:
                seen.add(dept_code)
                db.add(Department(
                    department_code=dept_code,
                    department_name=dept_name or dept_code,
                ))
                added = True
        if added:
            db.commit()
    finally:
        db.close()


def _backfill_spend_accounts() -> None:
    """Add any oracle_account_number values from spend that are missing from account_numbers (idempotent)."""
    from src.models.reference import AccountNumber
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        existing = {a.account_number for a in db.query(AccountNumber.account_number).all()}
        rows = db.execute(
            select(
                Spend.oracle_account_number,
                Spend.oracle_account_group,
                Spend.oracle_account_sub_group,
                Spend.oracle_cost_element,
            ).distinct()
        ).all()
        seen: set[str] = set()
        added = False
        for row in rows:
            acct_num, acct_group, acct_sub, cost_elem = row[0], row[1], row[2], row[3]
            if acct_num and acct_num not in existing and acct_num not in seen:
                seen.add(acct_num)
                db.add(AccountNumber(
                    account_number=acct_num,
                    account_desc=_build_account_desc(acct_group, acct_sub, cost_elem),
                    account_group=acct_group,
                    account_sub_group=acct_sub,
                    cost_element=cost_elem,
                ))
                added = True
        if added:
            db.commit()
    finally:
        db.close()


def _backfill_account_desc() -> None:
    """Populate account_desc for existing rows where it is NULL (idempotent)."""
    from src.models.reference import AccountNumber

    db = SessionLocal()
    try:
        nulls = db.query(AccountNumber).filter(AccountNumber.account_desc.is_(None)).all()
        for acct in nulls:
            acct.account_desc = _build_account_desc(acct.account_group, acct.account_sub_group, acct.cost_element)
        if nulls:
            db.commit()
    finally:
        db.close()
