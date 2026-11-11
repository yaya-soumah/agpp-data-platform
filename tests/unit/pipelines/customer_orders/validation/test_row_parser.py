from agpp.pipelines.customer_orders.validation.result import RejectionStage
from agpp.pipelines.customer_orders.validation.row_parser import parse_records
from agpp.shared.extraction import RawRecord

VALUES = {
    "order_id": "O-1001",
    "line_number": "1",
    "customer_id": "cus-00042",
    "customer_name": "Marie Dupont",
    "customer_country": "lu",
    "ordered_at": "2026-11-09T10:00:00Z",
    "product_id": "sup-001:s1-00012",
    "quantity": "3",
    "unit_price": "12.50",
    "currency": "eur",
    "status": "placed",
    "updated_at": "2026-11-09T11:00:00Z",
}


def _record(line: int = 2, problem: str | None = None, **overrides: str) -> RawRecord:
    return RawRecord(line, {**VALUES, **overrides}, problem)


def test_a_valid_record_is_parsed_and_normalized() -> None:
    parsed, rejected = parse_records("orders.csv", [_record()])

    assert rejected == []
    assert parsed[0].line_number == 2
    assert parsed[0].line.product_id == "SUP-001:S1-00012"
    assert parsed[0].raw["currency"] == "eur"


def test_structural_problems_from_extraction_are_rejected() -> None:
    parsed, rejected = parse_records("orders.csv", [_record(problem="expected 12 fields, found 9")])

    assert parsed == []
    assert rejected[0].reasons == ("expected 12 fields, found 9",)
    assert rejected[0].stage is RejectionStage.PARSING


def test_every_field_problem_is_reported() -> None:
    _, rejected = parse_records("orders.csv", [_record(line=7, quantity="0", currency="EURO")])

    assert rejected[0].line_number == 7
    assert any(reason.startswith("quantity") for reason in rejected[0].reasons)
    assert any(reason.startswith("currency") for reason in rejected[0].reasons)
    assert rejected[0].source_id == "orders.csv"


def test_reasons_do_not_echo_the_offending_value() -> None:
    _, rejected = parse_records("orders.csv", [_record(quantity="secret-value")])

    assert "secret-value" not in " ".join(rejected[0].reasons)


def test_blank_required_cells_are_rejected() -> None:
    _, rejected = parse_records("orders.csv", [_record(customer_name="  ")])

    assert any(reason.startswith("customer_name") for reason in rejected[0].reasons)


def test_unknown_columns_are_ignored() -> None:
    parsed, rejected = parse_records("orders.csv", [_record(color="red")])

    assert rejected == []
    assert len(parsed) == 1


def test_good_and_bad_records_are_separated_in_order() -> None:
    parsed, rejected = parse_records(
        "orders.csv", [_record(2), _record(3, quantity="x"), _record(4)]
    )

    assert [p.line_number for p in parsed] == [2, 4]
    assert [r.line_number for r in rejected] == [3]
