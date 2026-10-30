from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import pytest

from agpp.shared.database import Pool, connection
from agpp.shared.database.warehouse import UpsertResult, upsert

COLUMNS = ["widget_id", "name", "price"]
ROWS = [
    ("w1", "Alpha", Decimal("1.50")),
    ("w2", "Beta", Decimal("2.00")),
    ("w3", "Gamma", Decimal("3.25")),
]


@pytest.fixture
def widgets(scratch_pool: Pool) -> Pool:
    with connection(scratch_pool) as conn:
        conn.execute(
            """
            CREATE TABLE public.widget (
                widget_id text PRIMARY KEY,
                name text NOT NULL,
                price numeric(10, 2) NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    return scratch_pool


def _load(
    pool: Pool,
    rows: Sequence[Sequence[object]],
    update_columns: Sequence[str] | None = None,
    batch_size: int = 1000,
) -> UpsertResult:
    with connection(pool) as conn:
        return upsert(
            conn,
            schema="public",
            table="widget",
            columns=COLUMNS,
            conflict_columns=["widget_id"],
            rows=rows,
            update_columns=update_columns,
            batch_size=batch_size,
        )


def _snapshot(pool: Pool) -> list[tuple[str, str, Decimal, datetime]]:
    with connection(pool) as conn:
        rows = conn.execute(
            "SELECT widget_id, name, price, updated_at FROM public.widget ORDER BY widget_id"
        ).fetchall()
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def test_first_load_inserts_every_row(widgets: Pool) -> None:
    result = _load(widgets, ROWS)

    assert (result.attempted, result.written, result.unchanged) == (3, 3, 0)
    assert [row[:3] for row in _snapshot(widgets)] == ROWS


def test_loading_the_same_input_twice_changes_nothing(widgets: Pool) -> None:
    _load(widgets, ROWS)
    before = _snapshot(widgets)

    result = _load(widgets, ROWS)

    assert (result.written, result.unchanged) == (0, 3)
    assert _snapshot(widgets) == before


def test_only_changed_rows_are_updated(widgets: Pool) -> None:
    _load(widgets, ROWS)
    before = _snapshot(widgets)
    changed = [ROWS[0], ("w2", "Beta v2", Decimal("2.00")), ROWS[2]]

    result = _load(widgets, changed)

    after = _snapshot(widgets)
    assert result.written == 1
    assert after[1][1] == "Beta v2"
    assert after[1][3] > before[1][3]
    assert after[0] == before[0]
    assert after[2] == before[2]


def test_empty_update_columns_keep_existing_values(widgets: Pool) -> None:
    _load(widgets, ROWS)

    result = _load(widgets, [("w1", "Renamed", Decimal("9.99"))], update_columns=[])

    assert result.written == 0
    assert _snapshot(widgets)[0][1] == "Alpha"


def test_large_loads_are_batched(widgets: Pool) -> None:
    rows = [(f"w{index:05d}", f"Name {index}", Decimal("1.00")) for index in range(2500)]

    result = _load(widgets, rows, batch_size=1000)

    assert result.written == 2500
    with connection(widgets) as conn:
        count = conn.execute("SELECT count(*) FROM public.widget").fetchone()
    assert count == (2500,)


def test_later_duplicate_in_the_input_wins(widgets: Pool) -> None:
    _load(widgets, [("w1", "First", Decimal("1.00")), ("w1", "Second", Decimal("1.00"))])

    assert _snapshot(widgets)[0][1] == "Second"


def test_an_empty_load_writes_nothing(widgets: Pool) -> None:
    assert _load(widgets, []) == UpsertResult(attempted=0, written=0)
