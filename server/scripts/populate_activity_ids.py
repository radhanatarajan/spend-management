"""
Assign ACAPEX-XXXXXXX / AOPEX-XXXXXXX activity IDs to all spend rows.

Grouping rules (rows sharing the same key get the same ID):
  1. Has purchase_order_number  → (expense_type, po_number, po_line)
  2. No PO, Employee Related    → (expense_type, oracle_department, oracle_cost_element, oracle_account_sub_group)
  3. No PO, all others          → (expense_type, vendor_name, oracle_cost_element, oracle_account_sub_group)

Counters are independent per prefix (ACAPEX / AOPEX), starting at 1.
"""
import pymysql

DB = dict(host="127.0.0.1", port=3306, user="spend_user", password="spend_pass", database="spend_management")


def build_group_key(row):
    (expense_type, po_number, po_line, dept, cost_element, sub_group, vendor) = row[2:]
    if po_number:
        return (expense_type, "PO", po_number or "", po_line or "")
    if cost_element == "Employee Related":
        return (expense_type, "EMP", dept or "", cost_element, sub_group or "")
    return (expense_type, "VND", vendor or "", cost_element, sub_group or "")


def prefix(expense_type):
    return "ACAPEX" if expense_type == "CAPEX" else "AOPEX"


def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, expense_type,
               expense_type, purchase_order_number, purchase_order_line_number,
               oracle_department, oracle_cost_element, oracle_account_sub_group, vendor_name
        FROM spend
        ORDER BY expense_type, id
    """)
    rows = cur.fetchall()

    group_to_id: dict = {}
    capex_counter = 0
    opex_counter = 0
    updates: list[tuple[str, int]] = []

    for row in rows:
        row_id = row[0]
        expense_type = row[1]
        key = build_group_key(row)

        if key not in group_to_id:
            pfx = prefix(expense_type)
            if pfx == "ACAPEX":
                capex_counter += 1
                seq = capex_counter
            else:
                opex_counter += 1
                seq = opex_counter
            group_to_id[key] = f"{pfx}-{seq:07d}"

        updates.append((group_to_id[key], row_id))

    cur.executemany("UPDATE spend SET activity_id = %s WHERE id = %s", updates)
    conn.commit()

    print(f"Updated {len(updates)} rows")
    print(f"  ACAPEX groups: {capex_counter}")
    print(f"  AOPEX groups:  {opex_counter}")

    # Quick verification
    cur.execute("SELECT COUNT(*) FROM spend WHERE activity_id IS NULL")
    nulls = cur.fetchone()[0]
    print(f"  Rows still NULL: {nulls}")

    cur.execute("""
        SELECT activity_id, COUNT(DISTINCT month_key) AS months
        FROM spend
        WHERE purchase_order_number IS NOT NULL
        GROUP BY activity_id
        ORDER BY months DESC
        LIMIT 5
    """)
    print("\nTop PO-based activities (most months):")
    for r in cur.fetchall():
        print(f"  {r[0]}  →  {r[1]} months")

    conn.close()


if __name__ == "__main__":
    main()
