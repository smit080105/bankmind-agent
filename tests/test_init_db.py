from app.database import get_conn
from scripts.init_db import main


def test_reseeding_preserves_related_records(monkeypatch, tmp_path):
    monkeypatch.setattr("app.database.DATABASE_PATH", tmp_path / "test.db")
    main()

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO fee_waiver_history
               (customer_id, fee_type, amount, waived_on)
               VALUES ('CUST1001', 'late_payment', 25.0, '2026-01-01')"""
        )
        conn.execute(
            "UPDATE customers SET full_name = 'Temporary Name' WHERE customer_id = 'CUST1001'"
        )

    main()

    with get_conn() as conn:
        customer = conn.execute(
            "SELECT full_name FROM customers WHERE customer_id = 'CUST1001'"
        ).fetchone()
        waiver_count = conn.execute(
            "SELECT COUNT(*) FROM fee_waiver_history WHERE customer_id = 'CUST1001'"
        ).fetchone()[0]

    assert customer["full_name"] == "Ananya Rao"
    assert waiver_count == 1
