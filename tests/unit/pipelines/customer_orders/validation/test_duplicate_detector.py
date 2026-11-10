from agpp.pipelines.customer_orders.models import OrderLine
from agpp.pipelines.customer_orders.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.customer_orders.validation.result import ParsedLine, RejectionStage

VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "CUS-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "LU",
    "ordered_at": "2026-11-09T08:00:00Z",
    "product_id": "SUP-001:S1-00012",
    "quantity": "2",
    "unit_price": "10.00",
    "currency": "EUR",
    "status": "placed",
    "updated_at": "2026-11-09T10:00:00Z",
}


def _line(number: int, **overrides: str) -> ParsedLine:
    return ParsedLine(number, {}, OrderLine.model_validate({**VALUES, **overrides}))


def test_distinct_lines_pass_through_in_order() -> None:
    lines = [_line(2, line_number="1"), _line(3, line_number="2"), _line(4, order_id="O-1002")]

    unique, rejected = remove_duplicates(lines, source_id="orders.csv")

    assert [line.line_number for line in unique] == [2, 3, 4]
    assert rejected == []


def test_the_latest_update_wins() -> None:
    older = _line(2, updated_at="2026-11-09T09:00:00Z")
    newer = _line(3, updated_at="2026-11-09T11:00:00Z", status="shipped")

    unique, rejected = remove_duplicates([newer, older], source_id="orders.csv")

    assert unique == [newer]
    assert rejected[0].line_number == 2
    assert rejected[0].stage is RejectionStage.DUPLICATE
    assert rejected[0].reasons == ("order_id: duplicate of line 3, which was kept",)


def test_on_a_tie_the_later_line_wins() -> None:
    first = _line(2)
    second = _line(5)

    unique, rejected = remove_duplicates([first, second], source_id="orders.csv")

    assert unique == [second]
    assert rejected[0].line_number == 2


def test_three_copies_leave_exactly_one() -> None:
    lines = [
        _line(2, updated_at="2026-11-09T09:00:00Z"),
        _line(3, updated_at="2026-11-09T12:00:00Z"),
        _line(4, updated_at="2026-11-09T10:00:00Z"),
    ]

    unique, rejected = remove_duplicates(lines, source_id="orders.csv")

    assert [line.line_number for line in unique] == [3]
    assert sorted(r.line_number for r in rejected) == [2, 4]
