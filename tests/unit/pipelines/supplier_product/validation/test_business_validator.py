from datetime import UTC, datetime, timedelta
from decimal import Decimal

from agpp.pipelines.supplier_product.config import QualityConfig
from agpp.pipelines.supplier_product.models import SupplierProduct
from agpp.pipelines.supplier_product.validation.business_validator import (
    validate_business_rules,
)
from agpp.pipelines.supplier_product.validation.result import ParsedRecord, RejectionStage

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
QUALITY = QualityConfig(
    max_reject_ratio=0.1,
    allowed_currencies=("EUR", "USD"),
    max_unit_price=Decimal("100"),
    future_tolerance_minutes=5,
)
VALUES = {
    "supplier_id": "SUP-001",
    "supplier_sku": "A-001",
    "product_name": "Hex Bolt",
    "category": "Fasteners",
    "unit_price": "10.00",
    "currency": "EUR",
    "lead_time_days": "7",
    "updated_at": "2026-11-03T11:00:00Z",
}


def _record(line: int = 2, **overrides: str) -> ParsedRecord:
    product = SupplierProduct.model_validate({**VALUES, **overrides})
    return ParsedRecord(line, {}, product)


def test_a_compliant_record_is_accepted() -> None:
    accepted, rejected = validate_business_rules([_record()], QUALITY, now=NOW)

    assert len(accepted) == 1
    assert rejected == []


def test_currencies_outside_the_allowed_list_are_rejected() -> None:
    accepted, rejected = validate_business_rules([_record(currency="JPY")], QUALITY, now=NOW)

    assert accepted == []
    assert rejected[0].stage is RejectionStage.BUSINESS
    assert rejected[0].reasons[0].startswith("currency: JPY is not allowed")


def test_prices_above_the_maximum_are_rejected_but_the_maximum_is_allowed() -> None:
    accepted, rejected = validate_business_rules(
        [_record(2, unit_price="100.00"), _record(3, unit_price="100.01")], QUALITY, now=NOW
    )

    assert [r.line_number for r in accepted] == [2]
    assert [r.line_number for r in rejected] == [3]
    assert rejected[0].reasons[0].startswith("unit_price")


def test_timestamps_beyond_the_tolerance_are_rejected() -> None:
    within = (NOW + timedelta(minutes=4)).isoformat()
    beyond = (NOW + timedelta(minutes=6)).isoformat()

    accepted, rejected = validate_business_rules(
        [_record(2, updated_at=within), _record(3, updated_at=beyond)], QUALITY, now=NOW
    )

    assert [r.line_number for r in accepted] == [2]
    assert rejected[0].reasons[0].startswith("updated_at")
    assert "in the future" in rejected[0].reasons[0]


def test_every_violated_rule_is_reported() -> None:
    _, rejected = validate_business_rules(
        [_record(currency="JPY", unit_price="999.00")], QUALITY, now=NOW
    )

    assert len(rejected[0].reasons) == 2
