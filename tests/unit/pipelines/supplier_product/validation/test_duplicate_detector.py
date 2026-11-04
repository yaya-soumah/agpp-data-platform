from agpp.pipelines.supplier_product.models import SupplierProduct
from agpp.pipelines.supplier_product.validation.duplicate_detector import remove_duplicates
from agpp.pipelines.supplier_product.validation.result import ParsedRecord, RejectionStage

VALUES = {
    "supplier_id": "SUP-001",
    "supplier_sku": "A-001",
    "product_name": "Hex Bolt",
    "category": "Fasteners",
    "unit_price": "10.00",
    "currency": "EUR",
    "lead_time_days": "7",
    "updated_at": "2026-11-01T10:00:00Z",
}


def _record(line: int, **overrides: str) -> ParsedRecord:
    return ParsedRecord(line, {}, SupplierProduct.model_validate({**VALUES, **overrides}))


def test_unique_records_pass_through_in_order() -> None:
    records = [_record(2, supplier_sku="A"), _record(3, supplier_sku="B")]

    unique, rejected = remove_duplicates(records)

    assert [r.line_number for r in unique] == [2, 3]
    assert rejected == []


def test_the_latest_updated_at_wins() -> None:
    older = _record(2, updated_at="2026-11-01T09:00:00Z")
    newer = _record(3, updated_at="2026-11-01T11:00:00Z")

    unique, rejected = remove_duplicates([newer, older])

    assert unique == [newer]
    assert rejected[0].line_number == 2
    assert rejected[0].stage is RejectionStage.DUPLICATE
    assert rejected[0].reasons == ("supplier_sku: duplicate of line 3, which was kept",)


def test_on_a_tie_the_later_line_wins() -> None:
    first = _record(2)
    second = _record(5)

    unique, rejected = remove_duplicates([first, second])

    assert unique == [second]
    assert rejected[0].line_number == 2


def test_normalized_skus_clash() -> None:
    padded = _record(2, supplier_sku=" ab-1 ", updated_at="2026-11-01T09:00:00Z")
    plain = _record(3, supplier_sku="AB-1", updated_at="2026-11-01T10:00:00Z")

    unique, rejected = remove_duplicates([padded, plain])

    assert unique == [plain]
    assert len(rejected) == 1


def test_three_copies_leave_exactly_one() -> None:
    records = [
        _record(2, updated_at="2026-11-01T09:00:00Z"),
        _record(3, updated_at="2026-11-01T12:00:00Z"),
        _record(4, updated_at="2026-11-01T10:00:00Z"),
    ]

    unique, rejected = remove_duplicates(records)

    assert [r.line_number for r in unique] == [3]
    assert sorted(r.line_number for r in rejected) == [2, 4]
