from agpp.shared.database import Pool, connection
from agpp.shared.database.rejects import store_rejects
from agpp.shared.validation import RejectedRecord, RejectionStage


def _rejected(
    source_id: str, line: int, stage: RejectionStage = RejectionStage.PARSING
) -> RejectedRecord:
    return RejectedRecord(source_id, line, stage, ("quantity: bad",), {"quantity": "x"})


def _store(
    pool: Pool,
    rejected: list[RejectedRecord],
    run_id: str = "run-1",
    pipeline: str = "customer_orders",
) -> int:
    with connection(pool) as conn:
        return store_rejects(conn, run_id=run_id, pipeline=pipeline, rejected=rejected)


def test_reasons_and_raw_values_are_stored_as_json(warehouse: Pool) -> None:
    _store(warehouse, [_rejected("orders.csv", 7, RejectionStage.BUSINESS)])

    with connection(warehouse) as conn:
        row = conn.execute(
            "SELECT pipeline, source_id, line_number, stage, reasons, raw_values"
            " FROM operational.rejected_records"
        ).fetchone()
    assert row == (
        "customer_orders",
        "orders.csv",
        7,
        "business",
        ["quantity: bad"],
        {"quantity": "x"},
    )


def test_nothing_to_store_stores_nothing(warehouse: Pool) -> None:
    assert _store(warehouse, []) == 0


def test_the_same_run_stores_a_line_only_once(warehouse: Pool) -> None:
    assert _store(warehouse, [_rejected("orders.csv", 7)]) == 1

    assert _store(warehouse, [_rejected("orders.csv", 7)]) == 0

    with connection(warehouse) as conn:
        count = conn.execute("SELECT count(*) FROM operational.rejected_records").fetchone()
    assert count == (1,)


def test_pipelines_and_runs_keep_their_own_rejects(warehouse: Pool) -> None:
    _store(warehouse, [_rejected("SUP-001", 7)], pipeline="supplier_product")
    _store(warehouse, [_rejected("SUP-001", 7)], pipeline="customer_orders")
    _store(warehouse, [_rejected("SUP-001", 7)], run_id="run-2")

    with connection(warehouse) as conn:
        count = conn.execute("SELECT count(*) FROM operational.rejected_records").fetchone()
    assert count == (3,)
