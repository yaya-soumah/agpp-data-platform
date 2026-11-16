from agpp.pipelines.inventory.validation.result import RejectionStage
from agpp.pipelines.inventory.validation.row_parser import parse_records
from agpp.shared.extraction import RawRecord

VALUES = {
    "location_code": "lu-01",
    "location_name": "Luxembourg Warehouse",
    "location_country": "lu",
    "product_id": "sup-001:s1-00012",
    "on_hand": "120",
    "reserved": "20",
    "reorder_point": "50",
    "updated_at": "2026-11-13T05:30:00Z",
}


def _record(position: int = 1, problem: str | None = None, **overrides: str) -> RawRecord:
    return RawRecord(position, {**VALUES, **overrides}, problem)


def test_a_valid_record_is_parsed_and_normalized() -> None:
    parsed, rejected = parse_records("feed", [_record()])

    assert rejected == []
    assert parsed[0].line_number == 1
    assert parsed[0].item.location_code == "LU-01"
    assert parsed[0].item.product_id == "SUP-001:S1-00012"
    assert parsed[0].raw["location_code"] == "lu-01"


def test_structural_problems_from_extraction_are_rejected() -> None:
    parsed, rejected = parse_records("feed", [_record(problem="item is not a JSON object")])

    assert parsed == []
    assert rejected[0].reasons == ("item is not a JSON object",)
    assert rejected[0].stage is RejectionStage.PARSING


def test_every_field_problem_is_reported() -> None:
    _, rejected = parse_records("feed", [_record(position=7, on_hand="x", reorder_point="-1")])

    assert rejected[0].line_number == 7
    assert any(reason.startswith("on_hand") for reason in rejected[0].reasons)
    assert any(reason.startswith("reorder_point") for reason in rejected[0].reasons)
    assert rejected[0].source_id == "feed"


def test_reasons_do_not_echo_the_offending_value() -> None:
    _, rejected = parse_records("feed", [_record(on_hand="secret-value")])

    assert "secret-value" not in " ".join(rejected[0].reasons)


def test_blank_values_are_rejected() -> None:
    _, rejected = parse_records("feed", [_record(location_name="  ")])

    assert any(reason.startswith("location_name") for reason in rejected[0].reasons)


def test_unknown_fields_are_ignored() -> None:
    parsed, rejected = parse_records("feed", [_record(color="red")])

    assert rejected == []
    assert len(parsed) == 1


def test_good_and_bad_records_are_separated_in_order() -> None:
    parsed, rejected = parse_records("feed", [_record(1), _record(2, on_hand="x"), _record(3)])

    assert [p.line_number for p in parsed] == [1, 3]
    assert [r.line_number for r in rejected] == [2]
