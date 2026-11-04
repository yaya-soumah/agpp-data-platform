from agpp.pipelines.supplier_product.extraction import RawRecord
from agpp.pipelines.supplier_product.validation.result import RejectionStage
from agpp.pipelines.supplier_product.validation.row_parser import parse_records

VALUES = {
    "supplier_sku": " a-001 ",
    "product_name": "Hex Bolt M8",
    "category": "Fasteners",
    "unit_price": "12.50",
    "currency": "eur",
    "min_order_quantity": "10",
    "lead_time_days": "7",
    "is_active": "true",
    "updated_at": "2026-11-01T10:00:00Z",
}


def _record(line: int = 2, problem: str | None = None, **overrides: str) -> RawRecord:
    return RawRecord(line, {**VALUES, **overrides}, problem)


def test_a_valid_record_is_parsed_and_normalized() -> None:
    parsed, rejected = parse_records("SUP-001", [_record()])

    assert rejected == []
    assert parsed[0].line_number == 2
    assert parsed[0].product.supplier_id == "SUP-001"
    assert parsed[0].product.supplier_sku == "A-001"
    assert parsed[0].product.currency == "EUR"
    assert parsed[0].raw["supplier_sku"] == " a-001 "


def test_structural_problems_from_extraction_are_rejected() -> None:
    parsed, rejected = parse_records("SUP-001", [_record(problem="expected 9 fields, found 7")])

    assert parsed == []
    assert rejected[0].reasons == ("expected 9 fields, found 7",)
    assert rejected[0].stage is RejectionStage.PARSING


def test_every_field_problem_is_reported() -> None:
    parsed, rejected = parse_records("SUP-001", [_record(line=7, unit_price="0", currency="EURO")])

    assert parsed == []
    assert rejected[0].line_number == 7
    assert any(reason.startswith("unit_price") for reason in rejected[0].reasons)
    assert any(reason.startswith("currency") for reason in rejected[0].reasons)
    assert rejected[0].raw["currency"] == "EURO"


def test_reasons_do_not_echo_the_offending_value() -> None:
    _, rejected = parse_records("SUP-001", [_record(unit_price="secret-value")])

    assert "secret-value" not in " ".join(rejected[0].reasons)


def test_blank_required_cells_are_rejected() -> None:
    _, rejected = parse_records("SUP-001", [_record(category="  ")])

    assert any(reason.startswith("category") for reason in rejected[0].reasons)


def test_blank_optional_cells_use_the_defaults() -> None:
    parsed, rejected = parse_records("SUP-001", [_record(min_order_quantity="", is_active="  ")])

    assert rejected == []
    assert parsed[0].product.min_order_quantity == 1
    assert parsed[0].product.is_active is True


def test_unknown_columns_and_a_file_supplier_id_are_ignored() -> None:
    parsed, rejected = parse_records("SUP-001", [_record(color="red", supplier_id="SUP-999")])

    assert rejected == []
    assert parsed[0].product.supplier_id == "SUP-001"


def test_good_and_bad_records_are_separated_in_order() -> None:
    parsed, rejected = parse_records(
        "SUP-001", [_record(2), _record(3, unit_price="x"), _record(4)]
    )

    assert [p.line_number for p in parsed] == [2, 4]
    assert [r.line_number for r in rejected] == [3]
